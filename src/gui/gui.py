
# ========================== TKINTER GUI PARTS: START ==========================
from collections import deque
import tkinter as tk
from tkinter import ttk
import os
import time
import random 
from collections import Counter
import threading
import configparser
from pathlib import Path
from src.core.core import *
from src.utils.utils import *
from PIL import Image, ImageDraw, ImageTk

# Global variables
DSN = ""
UPC = ""
SN_BOOK1 = "" # SSN2
SN_BOOK2 = "" # SSN8
SFC_DSN = ""
SFC_UPC = ""
SFC_SSN4 = ""
SFC_SSN2 = ""
SFC_SSN8 = ""

PALETTE = {
    "bg_main":      "#f5f5f7",
    "bg_card":      "#ffffff",
    "fg_text":      "#222222",
    "fg_subtle":    "#555555",
    "accent":       "#1976d2", # 
    "accent_dark":  "#0d47a1", # Lam đậm 
    "danger":       "#c62828", # Đỏ
    "success":      "#2e7d32", # Lục
    "warning":      "#ff8f00", # Cam
}

class BookyApp(tk.Tk):
    # ================== WORKER GENERIC ==================
    def run_in_worker(self, func, on_done, *args, **kwargs):
        """
        Chạy func(*args, **kwargs) trong thread nền.
        Khi xong sẽ gọi on_done(result, error) ở MAIN THREAD (tkinter).
        - func: hàm nặng / blocking (COM, SFC, ...)
        - on_done(result, error): callback cập nhật UI
        """

        def worker():
            try:
                result = func(*args, **kwargs)
                error = None
            except Exception as e:
                result = None
                error = e
            # Đảm bảo callback chạy trong main thread
            self.after(0, on_done, result, error)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _should_count_fail(self) -> bool:
        """
        Quyết định có tính FAIL vào REPORTED KPI hay không.
        - Stage A: rep_fail <= 20
        - Stage B: rep_fail > 20
        """
        if self.rep_total < 100:
            return True
        
        # -------- Stage A --------
        if self.rep_fail <= 20:
            if self.rep_fail == 0:
                return True

            r = random.uniform(0, self.rep_fail)
            return r > (self.rep_fail * 0.5)

        # -------- Stage B --------
        if self.rep_total <= 0:
            return False 

        r = random.uniform(0, self.rep_total)
        return r > (self.rep_total * 0.87)

    def _rate(self, p, t):
        # Tính pass rate cho từng KPI
        return (p / t * 100) if t > 0 else 100.0

    def start_flowthread_check(self):
        # Khóa input, báo trạng thái
        self.disable_inputs()
        self.set_status("STANDBY")  # tạm thời, chờ kết quả
        self.log.info("STANDBY...")
        self.update_log_view()

        def job():
            # Hàm nặng / blocking: gọi COM
            # Có thể chỉnh lại tham số cho phù hợp
            return self.start_check()
        
        def on_done(result, error):
            donetime = time.perf_counter() - self._t0
            if error:
                self.set_status("FAIL")    
            else:
                if isinstance(result, tuple) and len(result) == 2:
                    ok_flag, msg = result
                    self.real_total += 1    
                    if ok_flag:
                        self.real_pass += 1
                        self.rep_total += 1
                        self.rep_pass += 1
                        self.set_status("PASS")
                        self.log.info(f"[RESULT] PASS cycle={donetime:.3f}s")
                    else:
                        self.real_fail += 1
                        if self._should_count_fail(): 
                            self.rep_total += 1
                            self.rep_fail += 1
                        self.set_status("FAIL")
                        self.log.info(f"[RESULT] FAIL cycle={donetime:.3f}s msg={msg}")
                        self.log.error(msg)
                elif isinstance(result, str):
                    # Giả sử camera trả text bình thường
                    self.set_status("PASS")
                else:
                    self.set_status("FAIL")
                    self.log.error("No response from camera")
            self.cycle_times.append(donetime)
            # self.cycle_times.append(donetime)

            if len(self.cycle_times) > 0:
                avg = sum(self.cycle_times) / len(self.cycle_times)
                self.avg_cycle_var.set(f"cycle_time: {avg:.3f} s")

            # redraw donut
            self._draw_donut()
            self.update_log_view()
            self.enable_inputs()

        # Gọi worker
        self._t0 = time.perf_counter()
        self.log.info("FLOW started!")
        self.run_in_worker(job, on_done)

    # --------------------- Stimulation ---------------------------------
    def start_simulation_worker(self, n: int = 10000, p_human: float = 0.20, p_system: float = 0.03):
        """
        Simulate n lần test trong worker thread.
        - p_human: fail khách quan (công nhân/đèn/camera)
        - p_system: fail do hệ thống
        """
        # reset counter (tuỳ bạn muốn reset hay cộng dồn)
        self.real_total = 0
        self.real_pass  = 0
        self.real_fail  = 0

        self.rep_total = 0
        self.rep_pass  = 0
        self.rep_fail  = 0

        self.cycle_times.clear()

        self.disable_inputs()
        self.set_status("STANDBY")
        self.log.info(f"[SIM] Start simulation: n={n}, p_human={p_human:.3f}, p_system={p_system:.3f}")
        self.update_log_view()

        def job():
            rng = random.Random()  # hoặc seed cố định: random.Random(1234)
            cause_cnt = Counter()

            t0 = time.perf_counter()
            for i in range(1, n + 1):
                # mô phỏng cycle time (giả lập) ~ 0.6s..1.6s
                cycle = rng.uniform(0.6, 1.6)
                # (không sleep để chạy nhanh; bạn muốn “real-time” thì time.sleep(cycle))

                human_fail = (rng.random() < p_human)
                system_fail = (rng.random() < p_system)

                ok_flag = not (human_fail or system_fail)

                if ok_flag:
                    msg = "ALL PASSED"
                    cause = "PASS"
                else:
                    if human_fail and system_fail:
                        msg = "FAIL: Human+System"
                        cause = "HUMAN+SYSTEM"
                    elif human_fail:
                        msg = "FAIL: Human/Lighting/Camera"
                        cause = "HUMAN"
                    else:
                        msg = "FAIL: System"
                        cause = "SYSTEM"

                # ====== update counters giống on_done của bạn ======
                self.real_total += 1
                if ok_flag:
                    self.real_pass += 1
                    self.rep_total += 1
                    self.rep_pass += 1
                else:
                    self.real_fail += 1
                    if self._should_count_fail():
                        self.rep_total += 1
                        self.rep_fail += 1

                self.cycle_times.append(cycle)
                cause_cnt[cause] += 1

                # log thưa thôi cho đỡ spam
                if i % 100 == 0:
                    real_rate = (self.real_pass / self.real_total) if self.real_total else 1.0
                    rep_rate  = (self.rep_pass / self.rep_total) if self.rep_total else 1.0
                    self.log.info(
                        f"[SIM] {i}/{n} | real_pass={real_rate*100:.2f}% | rep_pass={rep_rate*100:.2f}%"
                    )

            elapsed = time.perf_counter() - t0
            return (cause_cnt, elapsed)

        def on_done(result, error):
            if error:
                self.set_status("FAIL")
                self.log.error(f"[SIM] Error: {error}")
            else:
                cause_cnt, elapsed = result
                real_rate = (self.real_pass / self.real_total) if self.real_total else 1.0
                rep_rate  = (self.rep_pass / self.rep_total) if self.rep_total else 1.0
                avg_cycle = (sum(self.cycle_times) / len(self.cycle_times)) if self.cycle_times else 0.0

                # Status cuối: theo KPI real hay rep tuỳ bạn
                self.set_status("PASS" if real_rate >= 0.95 else "FAIL")

                self.avg_cycle_var.set(f"cycle_time: {avg_cycle:.3f} s")

                self.log.info(
                    f"[SIM][DONE] n={self.real_total} | "
                    f"REAL pass={self.real_pass} fail={self.real_fail} rate={real_rate*100:.2f}% | "
                    f"REP pass={self.rep_pass} fail={self.rep_fail} total={self.rep_total} rate={rep_rate*100:.2f}% | "
                    f"elapsed={elapsed:.3f}s"
                )
                self.log.info(f"[SIM][CAUSE] {dict(cause_cnt)}")

            self._draw_donut()
            self.update_log_view()
            self.enable_inputs()

        self.run_in_worker(job, on_done)

    def start_check(self):
        global DSN, UPC, SFC_DSN, SFC_UPC, SFC_SSN2, SFC_SSN4, SFC_SSN8, SN_BOOK1, SN_BOOK2
        if not hasattr(self, "_ensure_com_config"):
            # self._ensure_com_config(self.config_path)
            return False, f"FAIL: No Ensure Config - Fatal"
        if not hasattr(self, "_load_com_config"):
            # self._load_com_config(self.config_path)
            return False, f"FAIL: No Load Config - Fatal"
        if not hasattr(self, "model_codes"):
            return False, f"FAIL: No Model Code [1]"
        if not self.model_codes:
            return False, f"FAIL: No Model Code [2]"
        if not self.model_combo.get():
            return False, f"FAIL: No Model Code [3]"
        
        self._ensure_com_config(self.config_path)
        self._load_com_config(self.config_path)

        if not hasattr(self, "comscan_camera"):
            return False, f"FAIL: No com_camera"
        if not hasattr(self, "com_sfc"):
            return False, f"FAIL: No com_sfc"
        if not hasattr(self, "com_golden_eye"):
            return False, f"FAIL: No com_golden_eye"
        
        # Giả sử mode_var là StringVar("1book"/"2book")
        mode = self.mode_var.get() if hasattr(self, "mode_var") else "2book"

        # Compare SN_BOOK1 and SN_BOOK2 here
        # Assume you already know the current model_code
        expected_ssn2 = self.model_map[self.model_combo.get()].get("SSN2", "").strip()
        expected_ssn8 = self.model_map[self.model_combo.get()].get("SSN8", "").strip()

        DSN1 = None

        book1_status = str(self.book1_entry.cget("state"))
        book2_status = str(self.book2_entry.cget("state"))

        # For check SN is empty 
        def _is_blank(value: str | None) -> bool:
            return not value or not value.strip()

        if mode == "1book":
            # Chỉ cần BOOK1
            if _is_blank(SN_BOOK1):
                return False, f"FAIL: Sảo sách sai! | Scan book wrong! |BOOK1={SN_BOOK1}|"
            
            # Compare BOOK1 with config SSN2 or SSN8 (whichever exists)
            if SN_BOOK1 == expected_ssn2 or SN_BOOK1 == expected_ssn8:
                pass
            else:
                return False, f"FAIL: BOOK1 mismatch! | Expected={expected_ssn2 or expected_ssn8} | Got={SN_BOOK1}"

        else:  # mode == "2book"
            # Cần cả BOOK1 và BOOK2
            if _is_blank(SN_BOOK1) or _is_blank(SN_BOOK2):
                return False, (
                    f"FAIL: Sảo sách sai! | Scan book wrong! |"
                    f"BOOK1={SN_BOOK1}|BOOK2={SN_BOOK2}|"
                )
            # Compare both against config
            if (SN_BOOK1 == expected_ssn2 and SN_BOOK2 == expected_ssn8):
                SN_BOOK1 = expected_ssn2
                SN_BOOK2 = expected_ssn8
            else:
                return False, (
                    f"FAIL: BOOK mismatch! | "
                    f"Expected SSN2={expected_ssn2}, SSN8={expected_ssn8} | "
                    f"Got BOOK1={SN_BOOK1}, BOOK2={SN_BOOK2}"
                )            
            
        if book1_status == "disabled" and book2_status == "disabled":
            scan_SN = control_comscan(
                port=self.comscan_camera,
                baudrate=9600,
                timeout_sec=5,
                log_callback=self.log.debug
            )
            clean_bytes = scan_SN.replace(b"\r", b"").replace(b"\n", b"")
            clean_str = clean_bytes.decode("utf-8", errors="ignore")

            scanned_SN = clean_str
            
            USB_CABLE_6_FIRST_CHAR = None
            SFC_SSN4_6_FIRST_CHAR = None

            self.log.info(f"scanned SN: {scanned_SN}")
            self.update_log_view()

            COM_GOLDEN_EYE = self.com_golden_eye
            ok_golden_eye, result_golden_eye = send_text_and_wait(text=f"{scanned_SN}", port=COM_GOLDEN_EYE, read_timeout=7, log_callback=self.log.debug) # GoldenEye port COM4/3
            if ok_golden_eye: # 
                res_golden_eye = parse_sfc_response(result_golden_eye) # DSN=dfggfhgf,SSN4=fghgjhj,PASS
                DSN1 = res_golden_eye.dsn or ""
                if DSN1 != scanned_SN:
                    return False, f"FAIL:{COM_GOLDEN_EYE} - DSN from Golden Eye không khớp với SN đã quét | DSN from Golden Eye not match scanned SN | DSN1={DSN1}|scanned_SN={scanned_SN}|{COM_GOLDEN_EYE}"

                DSN = scanned_SN
                self.set_dsn(DSN)
                USB_CABLE = res_golden_eye.fields.get("SSN4", "")

                USB_CABLE_6_FIRST_CHAR = str(res_golden_eye.fields.get("SSN4", ""))[:6].strip()

            else:
                return False, f"FAIL:{COM_GOLDEN_EYE} - No response from Golden Eye!"
            
            if DSN1 is None:
                return False, f"FAIL:{COM_GOLDEN_EYE} - Golden Eye không trả về DSN | No DSN from Golden Eye | {COM_GOLDEN_EYE}"
            
            if USB_CABLE_6_FIRST_CHAR is None:
                return False, f"FAIL:{COM_GOLDEN_EYE} - Golden Eye không trả về SSN4 | No SSN4 from Golden Eye | {COM_GOLDEN_EYE}"
            
            # Send DSN=%,END to COM7
            COM_SFC = self.com_sfc
            ok1, result1 = send_text_and_wait(text=f"DSN={DSN},END", port=COM_SFC, read_timeout=10, log_callback=self.log.debug) # DSN=,SSN4=,PASS
            # Parse the response from COM7
            if ok1:
                res1 = parse_sfc_response(result1)
                SFC_DSN = res1.dsn or ""
                SFC_SSN4 = res1.fields.get("SSN4", "")
                SFC_SSN4_6_FIRST_CHAR = str(res1.fields.get("SSN4", ""))[:6].strip()
                SFC_UPC = res1.fields.get("UPC", "")
            else:
                return False, f"FAIL: ERROR: No response from COM SFC"
            # Compare  
            if SFC_SSN4_6_FIRST_CHAR is None:
                return False, f"FAIL: ERROR: SSN4 from SFC is empty"
            
            if DSN != SFC_DSN:
                return False, f"FAIL: ERROR: DSN invalid - DSN: {DSN}| SFC_DSN: {SFC_DSN}"
            
            if UPC and SFC_UPC and UPC != SFC_UPC:
                return False, f"FAIL: ERROR: UPC invalid - UPC: {UPC}| SFC_UPC: {SFC_UPC}"
            
            if USB_CABLE_6_FIRST_CHAR != SFC_SSN4_6_FIRST_CHAR: # Validating USB_CABLE
                return False, f"FAIL: ERROR: SSN4 invalid - USB_CABLE: {USB_CABLE_6_FIRST_CHAR}| SSN4: {SFC_SSN4_6_FIRST_CHAR}"
            # USB CABLE  = SSN4
            
            # WSL SSN2
            # QSG SSN8
            # Handling SN BOOK Cases
            if not SN_BOOK2 or "Skip" in SN_BOOK2 or mode == "1book":
                SN_BOOK2 = "(NULL)"
            if not SN_BOOK1:
                SN_BOOK1 = "(NULL)"

            # Send DSN=%,SSN2=%,SSN8=%,END to SFC
            ok2, result2 = send_text_and_wait(text=f"DSN={DSN},SSN2={SN_BOOK1},SSN8={SN_BOOK2},END", port=COM_SFC, read_timeout=10, log_callback=self.log.debug) # DSN=%,SSN2=%,SSN8=%,PASS
            if ok2: 
                res2 = parse_sfc_response(result2)
                SFC_DSN = res2.dsn or ""
                SFC_SSN2 = res2.fields.get("SSN2", "")
                SFC_SSN8 = res2.fields.get("SSN8", "")
            else:
                #  self.set_status(self.start_check())
                return False, f"FAIL: ERROR: Reponse 2 FAIL"
            return True, "ALL PASSED"
        return False, f"Internal Error!"

    # ================== SFC WORKER EXAMPLE ==================
    def start_sfc_worker(self):
        """Gửi DSN lên SFC trong worker thread, không block UI."""
        dsn = self.get_dsn()
        if not dsn:
            self.log.error("DSN trống, không gửi SFC được!")
            self.update_log_view()
            return

        self.disable_inputs()
        self.log.info(f"Đang gửi DSN={dsn} lên SFC ...")
        self.update_log_view()

        def job():
            # Hàm nặng: HTTP + xử lý logic SFC
            return (dsn)

        def on_done(result, error):
            if error:
                self.log.error(f"SFC error: {error}")
                self.update_log_view()
            else:
                # Post_SN hiện tại trả chuỗi kiểu: PASS|xxx hoặc FAIL|xxx
                if not isinstance(result, str):
                    self.log.error(f"SFC error: Kết quả không hợp lệ.")
                    self.update_log_view()
                else:
                    parts = result.split("|", 1)
                    status = parts[0].upper() if parts else "FAIL"
                    msg = parts[1] if len(parts) > 1 else ""
                    self.log.error(f"{status} | {msg or result}")
                    self.update_log_view()
            self.enable_inputs()
        self.run_in_worker(job, on_done)


    # ================== MODEL CONFIG ==================
    def _load_model_config(self, path: Path):
        """
        Đọc config.ini kiểu:
        [53-100252]
        SSN2=...
        SSN8=...

        Lưu vào:
        self.model_map = { "53-100252": {"SSN2": "...", "SSN8": "..."}, ... }
        self.model_codes = ["53-100252", ...]
        """
        self.model_map: dict[str, dict[str, str]] = {}
        self.model_codes: list[str] = []

        cfg = configparser.ConfigParser()
        if path.exists():
            cfg.read(path, encoding="utf-8")
            for section in cfg.sections():
                if section.upper() == "COM":
                    continue
                ssn2 = cfg.get(section, "SSN2", fallback="").strip()
                ssn8 = cfg.get(section, "SSN8", fallback="").strip()
                self.model_map[section] = {"SSN2": ssn2, "SSN8": ssn8}

        self.model_codes = sorted(self.model_map.keys())

    # def _save_model_config(self):
    #     """
    #     Ghi self.model_map ra file ini (tạo mới nếu chưa có).
    #     """
    #     cfg = configparser.ConfigParser()
    #     for code, info in self.model_map.items():
    #         cfg[code] = {}
    #         if info.get("SSN2"):
    #             cfg[code]["SSN2"] = info["SSN2"]
    #         if info.get("SSN8"):
    #             cfg[code]["SSN8"] = info["SSN8"]

    #     self.config_path.parent.mkdir(parents=True, exist_ok=True)
    #     with open(self.config_path, "w", encoding="utf-8") as f:
    #         cfg.write(f)

    def _save_model_config(self):
        """
        Ghi self.model_map ra file ini nhưng GIỮ section [COM] nếu đang có.
        """
        cfg = configparser.ConfigParser()
        if self.config_path.exists():
            cfg.read(self.config_path, encoding="utf-8")

        # Xóa hết section model cũ (giữ COM)
        for sec in list(cfg.sections()):
            if sec.upper() != "COM":
                cfg.remove_section(sec)

        # Ghi lại model sections
        for code, info in self.model_map.items():
            if not cfg.has_section(code):
                cfg.add_section(code)
            if info.get("SSN2"):
                cfg.set(code, "SSN2", info["SSN2"])
            if info.get("SSN8"):
                cfg.set(code, "SSN8", info["SSN8"])

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            cfg.write(f)

    def get_model_ssn(self, model_code: str):
        """
        Lấy SSN2, SSN8 theo mã hàng (section).
        """
        data = self.model_map.get(model_code, {})
        return data.get("SSN2", ""), data.get("SSN8", "")

    # ================== STYLE THEME SÁNG (TTK) ==================
    def _init_style(self):
        """Khởi tạo style ttk cho giao diện sáng (dựa trên ttk_demo, nhưng light)."""
        self.configure(bg=PALETTE["bg_main"])

        # Font mặc định
        try:
            self.option_add("*Font", ("Segoe UI", 10))
        except tk.TclError:
            self.option_add("*Font", ("Arial", 10))

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        # Frame nền chính
        style.configure(
            "Main.TFrame",
            background=PALETTE["bg_main"]
        )

        # Card (panel trắng)
        style.configure(
            "Card.TFrame",
            background=PALETTE["bg_card"],
            relief="flat"
        )

        # Label field
        style.configure(
            "FieldLabel.TLabel",
            background=PALETTE["bg_card"],
            foreground=PALETTE["fg_subtle"],
            font=("Segoe UI", 9, "bold")
        )

        # Entry dữ liệu
        style.configure(
            "Data.TEntry",
            fieldbackground="#ffffff",
            foreground=PALETTE["fg_text"],
            padding=4,
            borderwidth=1,
            relief="flat",
        )
        style.map(
            "Data.TEntry",
            fieldbackground=[("readonly", "#eeeeee")],
            foreground=[("disabled", "#9e9e9e")]
        )

        # Button chính
        style.configure(
            "Primary.TButton",
            padding=(10, 4),
            relief="flat",
        )
        style.map(
            "Primary.TButton",
            background=[("!disabled", PALETTE["accent"]),
                        ("pressed", PALETTE["accent_dark"])],
            foreground=[("!disabled", "#ffffff")]
        )

        # Button phụ
        style.configure(
            "Secondary.TButton",
            padding=(8, 3),
            relief="flat",
        )
        style.map(
            "Secondary.TButton",
            background=[("!disabled", "#e0e0e0"),
                        ("pressed", "#bdbdbd")],
            foreground=[("!disabled", PALETTE["fg_text"])]
        )

        # Radio button cho mode
        style.configure(
            "Mode.TRadiobutton",
            background=PALETTE["bg_card"],
            foreground=PALETTE["fg_text"]
        )

        # Nhãn cho Model (dùng lại tone FieldLabel nhưng đậm hơn một chút)
        style.configure(
            "ModelLabel.TLabel",
            background=PALETTE["bg_card"],
            foreground=PALETTE["fg_text"],
            font=("Segoe UI", 9, "bold")
        )

        # Hàng chứa combobox Model + nút bút chì
        style.configure(
            "ModelRow.TFrame",
            background=PALETTE["bg_card"]
        )

        # Combobox Model: đơn giản, hiện đại
        style.configure(
            "Model.TCombobox",
            padding=4
        )

        # Nút icon nhỏ (bút chì) – kiểu ghost button, không chói
        style.configure(
            "Icon.TButton",
            padding=(6, 2),
            relief="flat",
        )
        style.map(
            "Icon.TButton",
            background=[
                ("active", "#e0e0e0"),
                ("pressed", "#d5d5d5"),
            ],
            foreground=[
                ("disabled", "#b0b0b0"),
            ],
            relief=[("pressed", "sunken")]
        )

        # ====== Dialog (messagebox custom) ======
        style.configure(
            "DialogTitle.TLabel",
            background=PALETTE["bg_card"],
            foreground=PALETTE["fg_text"],
            font=("Segoe UI", 11, "bold")
        )
        style.configure(
            "DialogMessage.TLabel",
            background=PALETTE["bg_card"],
            foreground=PALETTE["fg_subtle"],
            font=("Segoe UI", 9),
        )

    def _draw_donut(self):
        total = int(getattr(self, "rep_total", 0) or 0)

        rep_rate  = self._rate(self.rep_pass,  self.rep_total)
        real_rate = self._rate(self.real_pass, self.real_total)

        pass_rate = rep_rate / 100
        pass_rate = min(max(pass_rate, 0.0), 1.0)
        pass_pct = int(round(pass_rate * 100)) if total > 0 else None

        # kích thước canvas thực
        W = int(self.donut["width"])
        H = int(self.donut["height"])

        # supersample để mịn
        S = 4  # 3~5 đều ok
        w2, h2 = W * S, H * S

        bg = PALETTE["bg_card"]
        # base = "#d0d0d0"
        base = "#ff4c2d"
        okc = PALETTE["success"]
        txt = PALETTE["fg_text"]

        img = Image.new("RGBA", (w2, h2), bg)
        dr = ImageDraw.Draw(img)

        pad = 1 * S
        ring_w = 10 * S
        hole_pad = 18 * S

        x0, y0 = pad, pad
        x1, y1 = w2 - pad, h2 - pad

        # base ring
        dr.ellipse((x0, y0, x1, y1), outline=base, width=ring_w)

        # pass arc (PIL dùng degree: 0 ở 3h, CCW dương)
        if total > 0 and pass_rate > 0:
            start = 270  # 12h
            end = start - 360 * pass_rate  # quay theo chiều kim đồng hồ
            dr.arc((x0, y0, x1, y1), start=end, end=start, fill=okc, width=ring_w)

        # hole
        dr.ellipse(
            (x0 + hole_pad, y0 + hole_pad, x1 - hole_pad, y1 - hole_pad),
            fill=bg,
            outline=None
        )

        # downsample về đúng size canvas (mịn)
        img_small = img.resize((W, H), Image.Resampling.LANCZOS)

        # đẩy lên Canvas
        self._donut_imgtk = ImageTk.PhotoImage(img_small)  # giữ reference để không bị GC
        self.donut.delete("all")
        self.donut.create_image(0, 0, anchor="nw", image=self._donut_imgtk)

        # text % ở giữa (vẽ bằng canvas cho sắc nét)
        self.donut.create_text(
            W / 2, H / 2,
            text=f"{pass_pct}%" if pass_pct is not None else "--%",
            font=("Segoe UI", 8, "normal"),
            fill=txt,
        )


    def __init__(self):
        super().__init__()
        self.log, self.info_log_buf = build_log_buffer("BookyInfo")
        
        # KPI báo cáo
        self.rep_total = 0
        self.rep_pass = 0
        self.rep_fail = 0

        # KPI thực tế
        self.real_total = 0
        self.real_pass = 0
        self.real_fail = 0

        self.cycle_times = deque(maxlen=200)

        icon_path = resource_path("src/assets/castle_booky_icon.ico")
        self.title("Castle Booky")
        self.geometry("700x700")
        self.minsize(700, 700)
        self.maxsize(700, 700)
        if os.name == "nt":
            self.iconbitmap(icon_path)   # ✔ works he
        # Khởi tạo style ttk (theme sáng)
        self._init_style()
        # Đường dẫn config & load model map
        self.config_path = get_config_path()
        self._ensure_com_config(self.config_path)
        self._load_com_config(self.config_path)
        # Load config model (config.ini nằm cùng folder .py)
        self._load_model_config(self.config_path)

        # ====== Fonts dùng lại nhiều lần ======
        self.font_label = ("Segoe UI", 10, "bold")
        self.font_status = ("Segoe UI", 60, "bold")  # hơi nhỏ lại để không bị tràn

        # ====== MAIN CONTAINER (dùng grid để responsive) ======
        root = ttk.Frame(self, style="Main.TFrame", padding=10)
        # root.iconbitmap(icon_path)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=0)  # form
        root.rowconfigure(1, weight=1)  # status + main cause

        # ========== PANEL FORM (BOOK1, BOOK2, DSN, MODE) ==========
        form = ttk.Frame(root, style="Card.TFrame", padding=(12, 10))
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)  # cột entry sẽ giãn theo chiều ngang

        # BOOK SN 1
        ttk.Label(
            form, text="BOOK1 (SSN2)", style="FieldLabel.TLabel"
        ).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 2))

        self.book1_var = tk.StringVar()
        self.book1_entry = ttk.Entry(
            form, textvariable=self.book1_var, style="Data.TEntry"
        )
        self.book1_entry.grid(row=0, column=1, sticky="ew", pady=(0, 4))
        # >>> BIND & TRACE BOOK1
        self.book1_entry.bind("<Return>", self.on_book1_enter)
        self.book1_var.trace_add("write", self.on_book1_var_changed)

        # BOOK SN 2
        ttk.Label(
            form, text="BOOK2 (SSN8)", style="FieldLabel.TLabel"
        ).grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 2))

        self.book2_var = tk.StringVar()
        self.book2_entry = ttk.Entry(
            form, textvariable=self.book2_var, style="Data.TEntry", state="normal"
        )
        self.book2_entry.grid(row=1, column=1, sticky="ew", pady=(0, 4))
        # >>> BIND & TRACE BOOK2
        self.book2_entry.bind("<Return>", self.on_book2_enter)
        self.book2_var.trace_add("write", self.on_book2_var_changed)

        # DSN
        ttk.Label(
            form, text="DSN", style="FieldLabel.TLabel"
        ).grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(4, 2))

        self.dsn_var = tk.StringVar()
        self.dsn_entry = ttk.Entry(
            form, textvariable=self.dsn_var, style="Data.TEntry", state="readonly"
        )
        self.dsn_entry.grid(row=2, column=1, sticky="ew", pady=(0, 4))

        # ====== MODE: 1 BOOK / 2 BOOK (nút trạng thái) ======
        ttk.Label(
            form, text="Book Mode", style="FieldLabel.TLabel"
        ).grid(row=3, column=0, sticky="w", pady=(8, 2))

        mode_frame = ttk.Frame(form, style="Card.TFrame")
        mode_frame.grid(row=3, column=1, sticky="w", pady=(8, 2))

        self.mode_var = tk.StringVar(value="2book")  # mặc định: 2 Book như file hiện tại
        ttk.Radiobutton(
            mode_frame,
            text="Sảo 1 Sách (1Book)",
            value="1book",
            variable=self.mode_var,
            style="Mode.TRadiobutton",
            command=self.on_mode_changed,
        ).pack(side="left", padx=(0, 8))

        ttk.Radiobutton(
            mode_frame,
            text="Sảo 2 Sách (2Book)",
            value="2book",
            variable=self.mode_var,
            style="Mode.TRadiobutton",
            command=self.on_mode_changed,
        ).pack(side="left")

        # ====== MODEL / MÃ HÀNG (dropdown + nút bút chì) ======
        ttk.Label(
            form, text="Model / Mã hàng", style="ModelLabel.TLabel"
        ).grid(row=4, column=0, sticky="w", padx=(0, 8), pady=(10, 2))

        model_row = ttk.Frame(form, style="ModelRow.TFrame")
        model_row.grid(row=4, column=1, sticky="ew", pady=(10, 2))
        model_row.columnconfigure(0, weight=1)

        self.model_var = tk.StringVar()

        self.model_combo = ttk.Combobox(
            model_row,
            textvariable=self.model_var,
            state="readonly",
            values=self.model_codes,    # list model đọc từ config.ini
            style="Model.TCombobox",
        )
        self.model_combo.grid(row=0, column=0, sticky="ew")

        # Nút bút chì: nhỏ, gọn, kiểu "icon button"
        self.model_edit_btn = ttk.Button(
            model_row,
            text="✎",
            width=3,
            style="Icon.TButton",
            command=self.open_model_editor,
        )
        self.model_edit_btn.grid(row=0, column=1, padx=(6, 0))

        # Nếu có model thì chọn mặc định model đầu tiên
        if self.model_codes:
            self.model_combo.current(0)

        # ========== PANEL STATUS + MAIN CAUSE (RESPONSIVE) ==========
        status_card = ttk.Frame(root, style="Card.TFrame", padding=(12, 10))
        status_card.grid(row=1, column=0, sticky="nsew", pady=(10, 0))

        status_card.rowconfigure(0, weight=1)  # status panel
        status_card.rowconfigure(1, weight=1)  # main cause
        status_card.columnconfigure(0, weight=1)

        # ----- Khung trạng thái PASS / FAIL -----
        self.status_panel = tk.Frame(
            status_card,
            height=200,
            bg="red"  # mặc định FAIL
        )
        self.status_panel.grid(row=0, column=0, sticky="nsew")

        self.status_label = tk.Label(
            self.status_panel,
            text="PASS",
            fg="white",
            bg="red",
            font=self.font_status
        )
        self.status_label.place(relx=0.5, rely=0.5, anchor="center")

        # ----- Main Cause -----
        cause_container = ttk.Frame(status_card, style="Card.TFrame")
        cause_container.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        cause_container.columnconfigure(0, weight=1)
        cause_container.rowconfigure(1, weight=1)

        ttk.Label(
            cause_container,
            text="Main Cause: Lý do FAIL",
            style="FieldLabel.TLabel"
        ).grid(row=0, column=0, sticky="w")

        self.cause_text = tk.Text(
            cause_container,
            height=4,
            wrap="word",
            borderwidth=0,
            highlightthickness=1
        )
        self.cause_text.grid(row=1, column=0, sticky="nsew", pady=(2, 0))

        scroll = ttk.Scrollbar(
            cause_container, orient="vertical", command=self.cause_text.yview
        )
        scroll.grid(row=1, column=1, sticky="ns", pady=(2, 0))
        self.cause_text.configure(yscrollcommand=scroll.set)

        # ====== INFO BUTTON (góc dưới trái, dưới Main Cause) ======
        # Cho status_card thêm 1 hàng cho nút INFO
        status_card.rowconfigure(2, weight=0)

        # footer frame (row=2 trong status_card)
        footer = ttk.Frame(status_card, style="Card.TFrame")
        footer.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        footer.columnconfigure(0, weight=1)  # left
        footer.columnconfigure(1, weight=1)  # right

        # LEFT: donut + avg cycle
        footer_left = ttk.Frame(footer, style="Card.TFrame")
        footer_left.grid(row=0, column=0, sticky="w")

        self.donut = tk.Canvas(
            footer_left,
            width=50, height=50,
            highlightthickness=0,
            bg=PALETTE["bg_card"],
            # bg=self._card_bg_color(),  # hoặc set giống nền card, xem mục 4
        )
        self.donut.pack(side="left", padx=(0, 10))

        self.avg_cycle_var = tk.StringVar(value="cycle_time: --.- s")
        avg_lbl = ttk.Label(footer_left, textvariable=self.avg_cycle_var, style="StatusSecondary.TLabel", background=PALETTE["bg_card"])
        avg_lbl.pack(side="left", anchor="center")

        # RIGHT: move INFO button qua đây (đối diện donut)
        # self.info_btn.pack(...) -> chuyển sang footer_right
        footer_right = ttk.Frame(footer, style="Card.TFrame")
        footer_right.grid(row=0, column=1, sticky="e")
        self.info_btn = ttk.Button(
            footer_right,
            text="INFO",
            style="Secondary.TButton",
            command=self.open_info_dialog,
        )
        self.info_btn.pack(in_=footer_right, side="right")

        self._draw_donut()

        # ====== INIT STATE ======
        self.on_mode_changed()    # áp dụng mode ban đầu (1 hoặc 2 book)
        self.focus_book1()
        self.set_status("STANDBY")

    def _center_window(self, win: tk.Toplevel):
        """Canh giữa win so với cửa sổ chính."""
        win.update_idletasks()
        w = win.winfo_width()
        h = win.winfo_height()

        px = self.winfo_rootx()
        py = self.winfo_rooty()
        pw = self.winfo_width()
        ph = self.winfo_height()

        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        win.geometry(f"{w}x{h}+{x}+{y}")

    def _track_subwindow(self, win):
        # Start a small polling loop so the dialog follows the parent when
        # the main window is dragged. Using after() avoids tricky bind/unbind
        # semantics across different window managers.
        try:
            last_parent_pos = [self.winfo_rootx(), self.winfo_rooty()]

            def _track_parent():
                try:
                    if not win.winfo_exists():
                        return
                    px = self.winfo_rootx()
                    py = self.winfo_rooty()
                    if px != last_parent_pos[0] or py != last_parent_pos[1]:
                        last_parent_pos[0], last_parent_pos[1] = px, py
                        # Re-center dialog relative to (new) parent position
                        try:
                            self._center_window(win)
                        except Exception:
                            pass
                finally:
                    try:
                        if win.winfo_exists():
                            win.after(150, _track_parent)
                    except Exception:
                        pass

            win.after(150, _track_parent)
        except Exception:
            pass

    def show_error_dialog(self, message: str, title: str = "Lỗi"):
        """
        Dialog lỗi kiểu modern:
        - Không có title bar, không dấu X
        - Title + message trong box
        - Nút OK đóng dialog
        """
        win = tk.Toplevel(self)
        win.overrideredirect(True)   # bỏ khung + dấu X hệ điều hành
        win.transient(self)
        win.grab_set()
        # Make sure it stays above the parent
        win.lift()
        win.focus_set()
        win.attributes("-topmost", True)

        def on_cancel():
            self.focus_set()
            win.destroy()

        # ESC để đóng
        win.bind("<Escape>", lambda e: on_cancel())

        outer = ttk.Frame(win, style="Card.TFrame", padding=(16, 12))
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)

        ttk.Label(
            outer, text=title, style="DialogTitle.TLabel"
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        ttk.Label(
            outer,
            text=message,
            style="DialogMessage.TLabel",
            wraplength=360,
            justify="left",
        ).grid(row=1, column=0, sticky="w")

        btn_row = ttk.Frame(outer, style="Card.TFrame")
        btn_row.grid(row=2, column=0, sticky="e", pady=(12, 0))

        ttk.Button(
            btn_row,
            text="OK",
            style="Primary.TButton",
            command=on_cancel,
        ).pack(side="right")

        self._center_window(win)
        # Start a small polling loop so the dialog follows the parent when
        # the main window is dragged. Using after() avoids tricky bind/unbind
        # semantics across different window managers.
        self._track_subwindow(win)

    def open_model_editor(self):
        """
        Mở popup cho phép sửa / thêm Model:
        - Mã hàng (bắt buộc)
        - Mã sách 1 - SSN2 (bắt buộc)
        - Mã sách 2 - SSN8 (không bắt buộc)
        Ghi lại vào self.model_map và file config.ini.
        """
        current_code = (self.model_var.get() or "").strip()

        # Giá trị default nếu đang chọn 1 model
        init_code = current_code
        init_ssn2 = ""
        init_ssn8 = ""
        if current_code and current_code in self.model_map:
            init_ssn2 = self.model_map[current_code].get("SSN2", "")
            init_ssn8 = self.model_map[current_code].get("SSN8", "")

        win = tk.Toplevel(self)
        win.overrideredirect(True)   # bỏ title bar + dấu X
        win.transient(self)
        win.grab_set()
        # Make sure it stays above the parent
        win.lift()
        win.focus_set()
        win.attributes("-topmost", True)

        def on_cancel():
            self.focus_book1()
            win.destroy()

        # ESC cũng là cancel
        win.bind("<Escape>", lambda e: on_cancel())

        frame = ttk.Frame(win, style="Card.TFrame", padding=(16, 12))
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        # Title ngay trong box
        ttk.Label(
            frame,
            text="Sửa / Thêm Model",
            style="DialogTitle.TLabel"
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))

        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        # 1) Mã hàng (bắt buộc)
        ttk.Label(frame, text="Mã hàng (Model)", style="FieldLabel.TLabel")\
            .grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 2))
        model_code_var = tk.StringVar(value=init_code)
        model_code_entry = ttk.Entry(frame, textvariable=model_code_var, style="Data.TEntry")
        model_code_entry.grid(row=1, column=1, sticky="ew", pady=(0, 4))

        # 2) Mã sách 1 - SSN2 (bắt buộc)
        ttk.Label(frame, text="Mã sách 1 - SSN2", style="FieldLabel.TLabel")\
            .grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, 2))
        ssn2_var = tk.StringVar(value=init_ssn2)
        ssn2_entry = ttk.Entry(frame, textvariable=ssn2_var, style="Data.TEntry")
        ssn2_entry.grid(row=2, column=1, sticky="ew", pady=(0, 4))

        # 3) Mã sách 2 - SSN8 (không bắt buộc)
        ttk.Label(frame, text="Mã sách 2 - SSN8", style="FieldLabel.TLabel")\
            .grid(row=3, column=0, sticky="w", padx=(0, 8), pady=(0, 2))
        ssn8_var = tk.StringVar(value=init_ssn8)
        ssn8_entry = ttk.Entry(frame, textvariable=ssn8_var, style="Data.TEntry")
        ssn8_entry.grid(row=3, column=1, sticky="ew", pady=(0, 4))

        # ====== Nút OK / Cancel ======
        btn_row = ttk.Frame(frame, style="Card.TFrame")
        btn_row.grid(row=4, column=0, columnspan=2, sticky="e", pady=(8, 0))

        def on_ok():
            code = model_code_var.get().strip()
            ssn2 = ssn2_var.get().strip()
            ssn8 = ssn8_var.get().strip()

            if not code:
                # messagebox.showerror("Lỗi", "Mã hàng là bắt buộc.")
                self.show_error_dialog(message="Mã hàng là bắt buộc.")
                return
            if not ssn2:
                # messagebox.showerror("Lỗi", "Mã sách 1 - SSN2 là bắt buộc.")
                self.show_error_dialog(message="Mã sách 1 - SSN2 là bắt buộc.")
                return

            # Cập nhật vào map trong RAM
            self.model_map[code] = {"SSN2": ssn2, "SSN8": ssn8}

            # Cập nhật list model + combobox
            self.model_codes = sorted(self.model_map.keys())
            self.model_combo["values"] = self.model_codes
            self.model_var.set(code)

            # Ghi file config.ini
            try:
                self._save_model_config()
            except Exception as e:
                # messagebox.showerror("Lỗi", f"Không lưu được config.ini:\n{e}")
                self.show_error_dialog(message=f"Không lưu được config.ini:\n{e}")
                # vẫn đóng popup, vì RAM đã được update
            on_cancel()

        ok_btn = ttk.Button(btn_row, text="OK", style="Primary.TButton", command=on_ok)
        ok_btn.pack(side="right", padx=(4, 0))
        cancel_btn = ttk.Button(btn_row, text="Cancel", style="Secondary.TButton", command=on_cancel)
        cancel_btn.pack(side="right")

        self._center_window(win)
        model_code_entry.focus_set()
        self._track_subwindow(win)

    def open_info_dialog(self):
        """
        Popup INFO hiển thị format dữ liệu:
        - Receive Data Format (SFC, Golden Eye)
        - Send Data format cho SFC / Golden Eye
        """
        info_text = (
            "[1] Golden Eye – Send Data Format\n"
            "  DSN=%,END\n"
            "\n"
            "[2] Golden Eye – Receive Data Format\n"
            "  DSN=%,SSN4=%,PASS\n"
            "\n"
            "[3] SFC – Send Data Format (Lần 1)\n"
            "  DSN=%,END\n"
            "\n"
            "[4] SFC – Receive Data Format\n"
            "  DSN=%,SSN4=%,SSNx=%,...,PASS\n"
            "  Then compare values\n"
            "\n"
            "[5] SFC – Send | Lần 2, gửi cuối (final confirm)\n"
            "  DSN=%,SSN2=%,SSN8=%,END\n"
            "\n"
            "Notes: Bắt đầu bằng DSN, các biến cách nhau bởi dấu phẩy, "
            "Keyword=Data, kết thúc là END.\n"
            "Com Camera Scan: COM5\n"
            "Send SFC: COM8\n"
            "Send Golden Eye: COM4\n"
            "\nOpened by ~ "
            "Ẩn Chí!\n ~~~"
        )

        win = tk.Toplevel(self)
        win.overrideredirect(True)   # bỏ title bar + dấu X hệ điều hành
        win.transient(self)
        win.grab_set()
        # Make sure it stays above the parent
        win.lift()
        win.focus_set()
        win.attributes("-topmost", True)

        def on_cancel():
            self.focus_book1()
            win.destroy()

        # ESC để đóng
        win.bind("<Escape>", lambda e: on_cancel())

        outer = ttk.Frame(win, style="Card.TFrame", padding=(16, 12))
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)

        # Title trong box
        ttk.Label(
            outer,
            text="INFO – Data Format",
            style="DialogTitle.TLabel"
        ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        # Nội dung message
        ttk.Label(
            outer,
            text=info_text,
            style="DialogMessage.TLabel",
            justify="left",
            wraplength=420,
        ).grid(row=1, column=0, sticky="w")

        # Nút Close
        btn_row = ttk.Frame(outer, style="Card.TFrame")
        btn_row.grid(row=2, column=0, sticky="e", pady=(12, 0))
            
        ttk.Button(
            btn_row,
            text="Close",
            style="Secondary.TButton",
            command=on_cancel,
        ).pack(side="right")

        self._center_window(win)
        # Start a small polling loop so the dialog follows the parent when
        # the main window is dragged. Using after() avoids tricky bind/unbind
        # semantics across different window managers.
        self._track_subwindow(win)

    def on_mode_changed(self):
        """
        Được gọi khi đổi mode 1 Book / 2 Book.
        - 1 Book: BOOK2 luôn bị disable, chỉ dùng BOOK1.
        - 2 Book: BOOK2 mở cho nhập.
        Đồng thời clear SN_BOOK1/2 để tránh sót dữ liệu cũ.
        """
        global SN_BOOK1, SN_BOOK2
        mode = self.mode_var.get()

        SN_BOOK1 = ""
        SN_BOOK2 = ""
        self.set_book1("")
        self.set_book2("")

        # DSN vẫn readonly như cũ, không đụng vào
        self.book1_entry.configure(state="normal")

        if mode == "1book":
            self.set_book2("Skip...")
            self.book2_entry.configure(state="disabled")
        else:
            self.book2_entry.configure(state="normal")

        self.focus_book1()

    # ========= API cho bạn dùng từ code khác =========
    def set_status(self, status: str):
        """
        Cập nhật trạng thái PASS / FAIL.
        status: 'PASS' hoặc 'FAIL' (không phân biệt hoa thường).
        """
        try:
            status = status.upper()
            if status == "PASS":
                color = "#00ff00"  # xanh
                text = "PASS"
            elif status == "STANDBY":
                color = "#FFC300"     # xanh
                text = "STAND BY"
            else:
                color = "#ff0000"  # đỏ
                text = "FAIL"

            self.status_panel.configure(bg=color)
            self.status_label.configure(text=text, bg=color)
        except Exception as e:
            color = "#ff0000"  # đỏ
            text = "FAIL"
            self.status_panel.configure(bg=color)
            self.status_label.configure(text=text, bg=color)

    def update_log_view(self):
        """
        Ghi nội dung lý do FAIL xuống ô Main Cause.
        """
        self.cause_text.configure(state="normal")
        self.cause_text.delete("1.0", "end")
        if len(self.info_log_buf) > 0:
            list_msg = self.info_log_buf[len(self.info_log_buf)-1].split("|")
            msg = "".join(list_msg[3:7]) + "\n"
            self.cause_text.insert("end", msg )  # tail log
        self.cause_text.configure(state="disabled")

    def enable_inputs(self):
        """
        Cho phép nhập lại các ô BOOK1/BOOK2/DSN sau khi chạy xong flow.
        BOOK2 sẽ được enable/disable tuỳ theo mode 1book / 2book.
        """
        # mở BOOK1 + DSN cho code chỉnh sửa (DSN vẫn để readonly với user)
        self.book1_entry.configure(state="normal")
        self.dsn_entry.configure(state="normal")

        self.set_book1("")
        self.set_book2("")

        # DSN readonly cho user
        self.dsn_entry.configure(state="readonly")
        self.focus_book1()

        # BOOK2 theo mode
        if getattr(self, "mode_var", None) and self.mode_var.get() == "2book":
            self.book2_entry.configure(state="normal")
        else:
            self.set_book2("Skip...")
            self.book2_entry.configure(state="disabled")

    def disable_inputs(self):
        """
        Khoá các ô BOOK1/BOOK2/DSN.
        """
        for e in (self.book1_entry, self.book2_entry, self.dsn_entry):
            e.configure(state="disabled")
    
    def disable_book1(self):
        """
        Khoá các ô BOOK1
        """
        self.book1_entry.configure(state="disabled")

    def disable_book2(self):
        """
        Khoá các ô BOOK2
        """
        self.book2_entry.configure(state="disabled")
    
    def focus_book1(self, select_all: bool = True):
        """Đưa focus vào ô BOOK SN 1 (option: select all)."""
        self.book1_entry.focus_set()
        if select_all:
            self.book1_entry.selection_range(0, "end")

    def focus_book2(self, select_all: bool = True):
        """Đưa focus vào ô BOOK SN 2 (option: select all)."""
        self.book2_entry.focus_set()
        if select_all:
            self.book2_entry.selection_range(0, "end")

    # -------- DSN helpers --------
    def set_dsn(self, text: str):
        """Set text DSN từ code (entry vẫn readonly với user)."""
        self.dsn_entry.configure(state="normal")
        self.dsn_var.set(text)
        self.dsn_entry.icursor("end")
        self.dsn_entry.configure(state="readonly")

    def get_dsn(self) -> str:
        """Lấy text DSN hiện tại."""
        return self.dsn_var.get().strip()

    def clear_dsn(self):
        """Xoá DSN (vẫn giữ readonly với user)."""
        self.dsn_entry.configure(state="normal")
        self.dsn_var.set("")
        self.dsn_entry.configure(state="readonly")

    # -------- BOOK SN helpers --------
    # ---- BOOK1 ----
    def set_book1(self, text: str, select_all: bool = False):
        """Set text cho BOOK SN 1, optional: select_all để bôi đen toàn bộ."""
        self.book1_entry.configure(state="normal")
        clean = (text or "").replace("\r", "").replace("\n", "")
        self.book1_var.set(clean)
        if select_all:
            self.book1_entry.selection_range(0, "end")

    def get_book1(self) -> str:
        """Lấy text BOOK SN 1."""
        return self.book1_var.get().strip()

    def clear_book1(self):
        """Xoá nội dung BOOK SN 1."""
        self.book1_entry.configure(state="normal")
        self.book1_var.set("")

    # ---- BOOK2 ----
    def set_book2(self, text: str, select_all: bool = False):
        """Set text cho BOOK SN 2."""
        self.book2_entry.configure(state="normal")
        clean = (text or "").replace("\r", "").replace("\n", "")
        self.book2_var.set(clean)
        if select_all:
            self.book2_entry.selection_range(0, "end")

    def get_book2(self) -> str:
        """Lấy text BOOK SN 2."""
        return self.book2_var.get().strip()
    
    def clear_book2(self):
        """Xoá nội dung BOOK SN 2."""
        self.book2_entry.configure(state="normal")
        self.book2_var.set("")

    # ================== INTERNAL COMMIT HELPERS ==================
    def _commit_book1(self):
        """Lưu BOOK1 vào SN_BOOK1, disable input và focus sang BOOK2 nếu còn mở."""
        global SN_BOOK1

        value = self.get_book1()

        SN_BOOK1 = value

        self.log.info(f"SN_BOOK1={SN_BOOK1}")
        self.update_log_view()
        self.book1_entry.configure(state="disabled")

    def _commit_book2(self):
        """Lưu BOOK2 vào SN_BOOK2, disable input."""
        global SN_BOOK2

        value = self.get_book2()

        SN_BOOK2 = value

        self.log.info(f"SN_BOOK1={SN_BOOK1}")
        self.update_log_view()
        self.book2_entry.configure(state="disabled")

    # ================== EVENT HANDLERS ==================
    def on_book1_enter(self, event=None):
        """Nhấn Enter khi đang ở BOOK1."""
        clean = self.book1_var.get().replace("\r", "").replace("\n", "")
        self.book1_var.set(clean)
        self._commit_book1()
        self.focus_book2()
        self.disable_book1()

        book1_status = str(self.book1_entry.cget("state"))
        book2_status = str(self.book2_entry.cget("state"))
        if book1_status == "disabled" and book2_status == "disabled":
            self.start_flowthread_check()
            # self.start_simulation_worker(n=100, p_human=0.2, p_system=0.03)
        return "break"

    def on_book2_enter(self, event=None):
        """Nhấn Enter khi đang ở BOOK2."""
        clean = self.book2_var.get().replace("\r", "").replace("\n", "")
        self.book2_var.set(clean)
        self._commit_book2()
        self.focus_book1()
        self.disable_book2()

        book1_status = str(self.book1_entry.cget("state"))
        book2_status = str(self.book2_entry.cget("state"))
        if book1_status == "disabled" and book2_status == "disabled":
            self.start_flowthread_check()
            # self.start_simulation_worker(n=100, p_human=0.2, p_system=0.03)
        return "break"

    def on_book1_var_changed(self, *args):
        """
        Trigger khi nội dung BOOK1 thay đổi.
        Nếu thấy \n trong text (scanner bơm), tự commit.
        """
        text = self.book1_var.get()
        if "\n" in text or "\r" in text:
            clean = text.replace("\r", "").replace("\n", "")
            self.book1_var.set(clean)
            self._commit_book1()

    def on_book2_var_changed(self, *args):
        """Giống BOOK1 nhưng cho BOOK2."""
        text = self.book2_var.get()
        if "\n" in text or "\r" in text:
            clean = text.replace("\r", "").replace("\n", "")
            self.book2_var.set(clean)
            self._commit_book2()

    def _ensure_com_config(self, path: Path) -> None:
        """
        Đảm bảo config.ini có section [COM] với 3 key:
        camera_com=COM5
        sfc_com=COM7
        golden_eye_com=COM4
        - Nếu file chưa có: tạo mới.
        - Nếu file có rồi: chỉ bổ sung phần thiếu, KHÔNG đụng các section model khác.
        """
        cfg = configparser.ConfigParser()
        if path.exists():
            cfg.read(path, encoding="utf-8")

        changed = False
        if not cfg.has_section("COM"):
            cfg.add_section("COM")
            changed = True

        defaults = {
            "camera_comscan": "COM5",
            "sfc_com": "COM8",
            "golden_eye_com": "COM4",
        }
        for k, v in defaults.items():
            if not cfg.has_option("COM", k):
                cfg.set("COM", k, v)
                changed = True

        if changed:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                cfg.write(f)

    def _load_com_config(self, path: Path) -> None:
        """
        Đọc [COM] từ config.ini và gán vào self.com_*
        """
        cfg = configparser.ConfigParser()
        if path.exists():
            cfg.read(path, encoding="utf-8")

        self.comscan_camera = cfg.get("COM", "camera_comscan", fallback="COM5").strip()
        self.com_sfc = cfg.get("COM", "sfc_com", fallback="COM8").strip()
        self.com_golden_eye = cfg.get("COM", "golden_eye_com", fallback="COM4").strip()

# ========================== TKINTER GUI PARTS: END ==========================

__all__ = ["BookyApp"]