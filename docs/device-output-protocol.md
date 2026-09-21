# 设备输出与灯控驱动协议

本文记录 LumaFlow 编辑器与灯控发射器之间的**控制链路**与**驱动数据协议**，包含当前实现与已移除的历史实现，便于下位机固件对接、回归验证和旧设备兼容。

> 说明：本文只描述「编辑器 → 发射器」的控制链路。发射器到荧光棒的 **433MHz 空口调制完全由下位机固件负责**，编辑器不做载波频率、信道或跳频控制（见文末「433MHz 空口」）。

---

## 1. 传输方式

通过 **视图 → 设备输出** 打开发射器控制面板。三种传输方式承载**完全相同**的应用层帧：

| 方式 | 适用场景 | 连接参数 |
|------|----------|----------|
| Serial | 固定控制台、调试（优先推荐） | 串口名 + 波特率，连接后静默 `SERIAL_CONNECT_SETTLE_SEC = 0.15s` |
| BLE | 近距离无线控制 | 设备名以 `LumaFlow` 开头；需 `bleak` |
| UDP | 同一局域网远距离布置 | IPv4 主机 + 固定端口 `32712` |

### 1.1 串口参数

波特率可选 `115200 / 230400 / 512000 / 460800 / 921600`，默认 `512000`，`timeout = 1s`。
AUTH 帧在串口上重复发送 `SERIAL_AUTH_REPEATS = 3` 次，间隔 `SERIAL_AUTH_REPEAT_DELAY_SEC = 0.05s`；STREAM 帧不重复。

### 1.2 BLE 参数

```
BLE_SERVICE_UUID        = 7e570001-3e74-4b1e-b6f4-1a91f7080001
BLE_CHARACTERISTIC_UUID = 7e570002-3e74-4b1e-b6f4-1a91f7080002   # 写入特征
BLE_NAME_PREFIX         = "LumaFlow"
BLE_SCAN_TIMEOUT_SEC    = 8.0
BLE_CONNECT_TIMEOUT_SEC = 10.0
BLE_WRITE_TIMEOUT_SEC   = 1.0
BLE_DISCONNECT_TIMEOUT_SEC = 2.0
BLE_FALLBACK_WRITE_CHUNK   = 20   # 无 write-without-response 时按 20 字节分片
```

扫描过滤规则：设备名以 `LumaFlow` 开头**为主**，广播包含上述 Service UUID 作为兼容补充。

### 1.3 UDP 参数

```
UDP_DEFAULT_PORT      = 32712     # 固定，不接受自定义端口
UDP_STREAM_REPEATS    = 2         # 可调范围 1..4
UDP_AUTH_REPEATS      = 3
UDP_REPEAT_DELAY_SEC  = 0.002
```

UDP 会对 AUTH 与 STREAM 做**轻量重复发送**以对抗偶发丢包；下位机负责按帧内容/序号去重，避免把重复 STREAM 再次发射成 433MHz 空口帧。允许输入的 `host:port` 形式中端口必须等于 `32712`，否则报错。

---

## 2. 当前协议：TLV 帧

实现位置：`core/serial_protocol.py`（组帧）、`core/serial_device_manager.py`（传输与重发）。

### 2.1 通用帧格式

```
偏移  长度        字段
0     2          TLV_HEAD = 0xEB 0x90
2     1          length   = 1 + len(payload)          // 含 cmd 自身
3     1          cmd                                    // TLV_CMD_OFFSET = 3
4     N          payload
4+N   1          checksum = (length + cmd + sum(payload)) & 0xFF
5+N   1          TLV_TAIL = 0xED
```

约束：

- `cmd` 单字节；`payload` 最长 127 字节（`length ≤ 128`，可放入单字节）
- 校验为 8 位截断和，覆盖 `length`、`cmd` 与全部 payload 字节的算术和

已定义命令：

| 命令 | 值 | 用途 |
|------|-----|------|
| `CMD_STREAM` | `0xD8` | 逐帧灯光数据 |
| `CMD_AUTH` | `0xE0` | 授权认证 |

### 2.2 `CMD_STREAM`（0xD8）— 灯光数据帧

payload 为**固定 20 字节**（`STREAM_PAYLOAD_LENGTH = 20`），10 个通道 × 2 字节：

```
每通道 2 字节：
  高字节 = (function << 4) | red
  低字节 = (green    << 4) | blue

  function / red / green / blue 均为 4-bit（0..15）
```

字段均按 `ch0..ch9` 从时间轴当前帧读取，越界（不在 `0..15`）直接抛错。完整 STREAM 帧长 = 2 + 1 + 1 + 20 + 1 + 1 = **26 字节**，其中 `length = 0x15`。

### 2.3 全局亮度调制

亮度**只在输出阶段**缩放 4-bit 颜色分量，不修改灯光序列数据，也不改变 `function`：

```python
GLOBAL_BRIGHTNESS_MIN = 0
GLOBAL_BRIGHTNESS_MAX = 100
GLOBAL_BRIGHTNESS_DEFAULT = 100

scaled = (value * brightness_percent + 50) // 100   # 确定性四舍五入（半进位）
```

`red / green / blue` 各自缩放，`function` 不缩放。

### 2.4 `CMD_AUTH`（0xE0）— 授权帧

payload 结构：

```
偏移  长度   字段
0     4      host_time     uint32 小端
4     4      expire_time   uint32 小端
8     1      sig_len       = len(signature)，范围 1..72
9     N      signature     原始字节
```

长度为 10..81 字节。约束：`host_time ≤ expire_time`，否则视为已过期并报错。

授权串（UI 中的 `AUTH LIC` 文本框）为文本格式：

```
MAC|expire_time|signature_hex
```

- `MAC`：12 个十六进制字符（→ 6 字节），允许大小写与分隔符，解析时只保留字母数字
- `expire_time`：十进制 Unix 时间戳，必须落在 uint32 范围
- `signature_hex`：偶数个十六进制字符，解码后 1..72 字节

连接成功后会发送 AUTH 数据；断开重连会重新认证。

### 2.5 帧节流与去重（编辑器侧）

`core/device_output_worker.py` 在独立线程中按播放位置发送：

```
offset_time = position_ms + device.offset_ms
frame_index = dm.get_frame_index_at_ms(offset_time)
仅当 frame_index != last_sent_frame_index 时才取帧并发送
发送成功后才更新 last_sent_frame_index
```

即同一帧不会重复下发；串口输出默认 offset 为 `200ms`，UI 提供 `-50 / -10 / +10 / +50 / Reset` 按钮微调。

---

## 3. 历史协议：22 字节定长包（v1.4.0 之前）

> 移除于提交 `94f2c3d`（`feat: Update version to 1.4.0 and enhance serial device management`）。
> 原实现：`app_logic.py` 的 `AppLogic.build_serial_packet()`，配合 `core/serial_device_manager.py`。

驱动层自述（旧文件 docstring）：

```text
Manager for USB Serial RF Transmitter device.
Sends 22-byte packets using the same protocol as LumaFlow_player_v2.
```

组帧逻辑：

```python
def build_serial_packet(self, frame):
    """Build 22-byte serial packet from frame data."""
    packet = bytearray()
    packet.append(0xC0)  # SOF
    for i in range(10):
        func = int(frame[f'ch{i}_function'])
        r = int(frame[f'ch{i}_red'])
        g = int(frame[f'ch{i}_green'])
        b = int(frame[f'ch{i}_blue'])
        high_byte = (func << 4) | r
        low_byte = (g << 4) | b
        packet.append(high_byte)
        packet.append(low_byte)
    packet.append(0xC1)  # EOF
    return bytes(packet)
```

帧格式：

```
偏移   长度  字段
0      1     0xC0            SOF 帧头
1..20  20    10 通道 × 2 字节
               高字节 = (function << 4) | red
               低字节 = (green    << 4) | blue
21     1     0xC1            EOF 帧尾
```

其余特征：

- 串口默认 `512000` baud，可选值与当前一致
- 同样使用 `last_sent_frame_index` 去重，`offset_ms` 语义与当前一致
- **无** AUTH 认证、**无** 全局亮度调制、**无** TLV 长度与校验字段

### 3.1 新旧协议映射

20 字节通道载荷**布局完全一致**，改动只在封装层：

| 项 | 旧（≤ v1.3.x） | 新（≥ v1.4.0） |
|----|----------------|----------------|
| 帧头 | `0xC0` | `0xEB 0x90` |
| 长度 | 隐式定长 22 | 显式 `length` 字节 |
| 命令 | 无 | `cmd` 字节（`0xD8` / `0xE0`） |
| 校验 | 无 | 8 位截断和 |
| 帧尾 | `0xC1` | `0xED` |
| 认证 | 无 | `CMD_AUTH` |
| 亮度调制 | 无 | 输出阶段 4-bit 缩放 |

因此下位机若已支持旧 22 字节包，只需在解析层替换为 TLV 拆包即可复用同一份通道解码逻辑。

---

## 4. 历史灯控驱动：键盘 / 灯条 HID（已移除）

> 同样移除于提交 `94f2c3d`：`core/keyboard_device_manager.py`（201 行）整文件删除，同时删除 `ui/device_output_dock.py` 中的 `KeyboardDevicePanel`、`app_logic.py` 中的 `keyboard_*` 槽与信号、`core/device_output_worker.py` 中的 keyboard 分支。

该驱动**不再使用原始 HID 报文**（代码注释原文：`No raw HID packets anymore`），而是逆向工程得到的 **gRPC-Web + protobuf** 接口：

```
端点        http://127.0.0.1:6015/iot_manager.IotManager/ControlDeviceLight
默认设备路径 \\?\HID#VID_3151&PID_504E&MI_02#8&ca262e&0&0000
              #{4d1e55b2-f16f-11cf-88cb-001111000030}
请求头       Content-Type / Accept: application/grpc-web-text
             x-grpc-web: 1
超时         0.5s
```

gRPC-Web-Text 封装：`[0x00 压缩标志][4 字节大端消息长度][protobuf payload]` → 整体 Base64 后作为请求体。

逆向出的请求消息：

```text
message ControlDeviceLightRequest {
  string      device_path = 1;   // 0x0A
  LightAction action      = 2;   // 0x10，ACTION_SET_LIGHT = 2
  RGB         rgb         = 3;   // 0x1A，3 × u8 (r, g, b)
  string      request_id  = 4;   // 0x22，UUID 字符串
}
```

行为要点：

- `connect()` 即发送一次 `ACTION_SET_LIGHT` 唤醒设备，成功后置 `is_initialized`
- `send_color(r, g, b)` 以 `last_rgb` 去重，成功发送后累加 `frames_sent` 并发出 `frame_sent`
- UI 可配置 `device_path`、`target_keyboard`、`target_lightstrip`、`selected_channel`（`-1` 表示 10 通道平均）、`offset_ms`
- RGB 由 4-bit 分量线性映射到 8-bit：单通道 `v * 255 / 15`，平均通道 `sum/10 * 255 / 15`

> 注：被删除时该实现与 worker 的调用约定并不完全一致（worker 调用 `send_frame(r, g, b)` 并写入 `last_sent_frame_index`，而管理器只提供 `send_color()`），且源码中标注 UI 设置项「尚未被 gRPC 实现使用」，属于未完成的实验性通路。

---

## 5. 433MHz 空口

仓库源码与全部历史中**不存在**任何设置 433MHz 载波频率、信道、跳频或射频寄存器写入的代码。相关表述仅出现在文档中：

- `README.md`：UDP 重复 STREAM 由下位机过滤，避免重复发送 **433MHz 空口帧**；「BLE、UDP 和串口只负责编辑器到发射器的控制链路；发射器到荧光棒仍使用 **433MHz**，需要单独完成天线覆盖测试」
- `CHANGELOG.md`（1.8.0）：同一表述

即：**433MHz 调制、频率与信道策略由下位机固件实现**，编辑器仅通过上述 TLV（或历史 22 字节）帧下发 10 通道的 `function + RGB` 数据。

---

## 6. 兼容性与变更约束

- 通道显示选择不得修改 CSV 或设备协议（见 `CONTRIBUTING.md`）。
- 设备输出改动需要独立的**实机验证**；`tests/test_serial_protocol.py` 只覆盖组帧与授权解析，不覆盖空口效果。
- 亮度调制只在输出阶段生效，不得回写灯光序列。
- 用户可见文字需同时更新 `resources/i18n/zh-CN.json` 与 `en-US.json`。

---

## 7. 源码索引

| 内容 | 位置 |
|------|------|
| TLV 组帧、授权解析、亮度缩放 | `core/serial_protocol.py` |
| Serial / BLE / UDP 传输、重发、扫描 | `core/serial_device_manager.py` |
| 后台发送线程、连接与认证流程 | `core/device_output_worker.py` |
| 设备输出面板 UI | `ui/device_output_dock.py` |
| 协议回归测试 | `tests/test_serial_protocol.py` |

历史实现复核（只读）：

```powershell
git show 94f2c3d^:core/serial_device_manager.py      # 旧 22 字节驱动
git show 94f2c3d^:app_logic.py                       # 旧 build_serial_packet()
git show 94f2c3d^:core/keyboard_device_manager.py    # 键盘/灯条 gRPC-Web 驱动
git show 94f2c3d --stat                              # 移除/新增清单
git diff 94f2c3d 9fc7150 -- core/serial_protocol.py  # 1.8.0 协议演进
```
