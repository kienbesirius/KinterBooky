from typing import Dict, Optional, NamedTuple
import re
import serial
import time
from src.utils.utils import *
# ========================== COM CAM SCANNER: control_comscan_camera START ==========================
def control_comscan(
    port: str = "COM5",
    baudrate: int = 9600,
    timeout_sec: float = 5.0,
    log_callback = print,
) -> bytes | None:
    # Lệnh: 16 54 0D (giả sử đây là HEX: 0x16 0x54 0x0D)
    cmd = bytes([0x16, 0x54, 0x0D])

    try:
        with serial.Serial(port, baudrate, timeout=0) as ser:
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.write(cmd)
            ser.flush()

            deadline = time.time() + timeout_sec
            recv = bytearray()

            while time.time() < deadline:
                if ser.in_waiting:
                    recv.extend(ser.read(ser.in_waiting))
                if recv:
                    break
                time.sleep(0.01)

            if recv:
                return bytes(recv) # GT542A0154530005
            else:
                return None

    except serial.SerialException as e:
        log_callback(f"[ERROR] Serial error on {port}: {e}")
        return None
# ========================== COM CAM SCANNER: control_comscan_camera END ==========================

# ========================== SFC Parser: START ==========================
class SFCResult(NamedTuple):
    dsn: Optional[str]
    status: Optional[str]
    fields: Dict[str, str]

def parse_sfc_response(raw: str,log_callback = print,) -> SFCResult:
    log_callback("Start Parsing")
    """
    Parse chuỗi SFC response kiểu:

        "SFC: DSN=,SSN4=,PASS"
        "SFC: DSN=ABC,SSN2=123,SSN8=XYZ,PASS"

    Separator có thể là: ',', '|' hoặc ';'.

    Trả về:
        SFCResult(dsn, status, fields_dict)
    """
    if raw is None:
        log_callback(f"Parsed: Get none response")
        return SFCResult(dsn=None, status=None, fields={})

    # Bỏ khoảng trắng đầu/đuôi + xuống dòng
    s = raw.strip()

    # Bỏ prefix "SFC:" nếu có
    if s.upper().startswith("SFC"):
        # SFC: ..., hoặc SFC , ...
        # tách ra phần sau dấu ':' nếu có
        parts = s.split(":", 1)
        if len(parts) == 2:
            s = parts[1].strip()
        else:
            # không có ':' thì cứ dùng lại s
            s = s[3:].lstrip(" :")

    # Tách token theo , ; | (có thể kèm khoảng trắng)
    tokens = [tok.strip() for tok in re.split(r"[,\|;]", s) if tok.strip()]

    fields: Dict[str, str] = {}
    dsn: Optional[str] = None
    status: Optional[str] = None

    for tok in tokens:
        # Nếu dạng key=value
        if "=" in tok:
            key, value = tok.split("=", 1)
            key = key.strip().upper()
            value = value.strip()
            fields[key] = value

            if key == "DSN":
                dsn = value
        else:
            # Không có '=', giả sử là status (PASS/ERRO/FAIL/…)
            upper_tok = tok.upper()
            if upper_tok in ("PASS", "ERRO", "FAIL", "ERROR"):
                status = upper_tok
            else:
                # token lạ thì có thể bỏ qua hoặc log lại tùy ý
                pass
    log_callback(f"Parsed: STATUS={status} | DSN={dsn} | FIELDS={fields}")
    return SFCResult(dsn=dsn, status=status, fields=fields)

# ========================== SFC Parser: END ==========================

# ========================== Send Text to COM(x): START ==========================
def send_text_and_wait(
    text: str,
    port: str = "COM7",
    baudrate: int = 9600,
    write_append_crlf: bool = True,
    read_timeout: float = 5.0,
    log_callback = print,
):
    """
    Gửi chuỗi text ra cổng COM rồi chờ response tối đa read_timeout giây.

    Return:
        (True, response_str)  nếu có nhận được dữ liệu
        (False, message)      nếu timeout hoặc lỗi
    """
    try:
        # timeout=0 để tự mình quản lý timeout bằng vòng while + time.time()
        with serial.Serial(port, baudrate, timeout=0) as ser:
            # ---- GỬI DỮ LIỆU ----
            send_str = text + ("\r\n" if write_append_crlf else "")
            ser.reset_input_buffer()
            ser.reset_output_buffer()
            ser.write(send_str.encode("utf-8"))
            ser.flush()

            # ---- CHỜ RESPONSE ----
            deadline = time.time() + read_timeout
            response = ""

            while time.time() < deadline:
                line = ser.readline()  # đọc theo \n, nếu thiết bị gửi dạng text
                if line:
                    try:
                        decoded = line.decode("utf-8")
                    except UnicodeDecodeError:
                        decoded = line.decode("latin-1", errors="ignore")

                    response += decoded
                    print(f"[debug][{port}] -> {decoded!r}")

                    if "PASS" in response or "ERRO" in response or "FAIL" in response:
                        break
                else:
                    time.sleep(0.01)

            if "FAIL" in response or "ERRO" in response:
                res = response.strip()
                return False, f"{port} FAIL - {res}"
            if response:
                return True, response.strip()
            return False, "No response (timeout)"

    except serial.SerialException as e:
        log_callback(f"[ERROR] Serial error on {port}: {e}")
        return False, f"Serial error: {e}"
# ========================== Send Text to COM(x): END ==========================

__all__ = [
    "control_comscan",
    "parse_sfc_response",
    "send_text_and_wait",
]