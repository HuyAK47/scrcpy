"""Unit tests for release/build_linux_gui_deb.sh debian packaging script."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

_repo_root = Path(__file__).resolve().parent.parent.parent
_build_script = _repo_root / "release" / "build_linux_gui_deb.sh"


class TestDebPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.has_dpkg_deb = shutil.which("dpkg-deb") is not None
        cls.has_shellcheck = shutil.which("shellcheck") is not None
        cls.has_desktop_validate = shutil.which("desktop-file-validate") is not None

    def test_bash_syntax(self):
        """Kiểm tra cú pháp bash của script bằng bash -n."""
        self.assertTrue(_build_script.is_file(), f"Script không tồn tại: {_build_script}")
        res = subprocess.run(
            ["bash", "-n", str(_build_script)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(res.returncode, 0, f"Lỗi cú pháp bash: {res.stderr}")

    def test_shellcheck(self):
        """Kiểm tra mã script bằng shellcheck nếu có trên máy."""
        if not self.has_shellcheck:
            self.skipTest("shellcheck không có sẵn trên hệ thống")
        res = subprocess.run(
            ["shellcheck", str(_build_script)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(res.returncode, 0, f"Lỗi shellcheck: {res.stdout}\n{res.stderr}")

    def test_missing_inputs_reports_error_and_guidance(self):
        """Thiếu file đầu vào bắt buộc -> exit khác 0 và hướng dẫn lệnh cần chạy."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            dist_dir = tmp_path / "dist"
            dist_dir.mkdir()
            output_dir = tmp_path / "output"
            output_dir.mkdir()
            server_file = tmp_path / "scrcpy-server"
            server_file.write_text("dummy-server")

            scrcpy_bin = dist_dir / "scrcpy"
            adb_bin = dist_dir / "adb"

            base_env = os.environ.copy()
            base_env["OUTPUT_DIR"] = str(output_dir)

            # Trường hợp 1: Thiếu scrcpy
            adb_bin.write_text("dummy-adb")
            adb_bin.chmod(0o755)
            if scrcpy_bin.exists():
                scrcpy_bin.unlink()
            env = base_env.copy()
            env["DIST_DIR"] = str(dist_dir)
            env["SERVER_PATH"] = str(server_file)
            res = subprocess.run(
                [str(_build_script)],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("release/build_linux.sh x86_64", res.stderr)

            # Trường hợp 2: Thiếu adb
            scrcpy_bin.write_text("dummy-scrcpy")
            scrcpy_bin.chmod(0o755)
            if adb_bin.exists():
                adb_bin.unlink()
            res = subprocess.run(
                [str(_build_script)],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("release/build_linux.sh x86_64", res.stderr)

            # Trường hợp 3: Thiếu scrcpy-server
            adb_bin.write_text("dummy-adb")
            adb_bin.chmod(0o755)
            env["SERVER_PATH"] = str(tmp_path / "non-existent-server")
            res = subprocess.run(
                [str(_build_script)],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("release/build_server.sh", res.stderr)

    def test_build_deb_package_success(self):
        """Tạo gói .deb thành công và kiểm tra file, quyền, control fields, desktop entry."""
        if not self.has_dpkg_deb:
            self.skipTest("dpkg-deb không có sẵn trên hệ thống")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            dist_dir = tmp_path / "dist"
            dist_dir.mkdir()
            output_dir = tmp_path / "output"
            output_dir.mkdir()

            # Giả lập output dist
            scrcpy_bin = dist_dir / "scrcpy"
            scrcpy_bin.write_text("#!/bin/sh\necho scrcpy")
            scrcpy_bin.chmod(0o755)

            adb_bin = dist_dir / "adb"
            adb_bin.write_text("#!/bin/sh\necho adb")
            adb_bin.chmod(0o755)

            (dist_dir / "scrcpy.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (dist_dir / "disconnected.png").write_bytes(b"\x89PNG\r\n\x1a\n")
            (dist_dir / "scrcpy.1").write_text("man page")
            (dist_dir / "LICENSE").write_text("Apache-2.0")

            server_file = tmp_path / "scrcpy-server"
            server_file.write_bytes(b"PK\x03\x04dummy-apk")

            env = os.environ.copy()
            env["DIST_DIR"] = str(dist_dir)
            env["SERVER_PATH"] = str(server_file)
            env["OUTPUT_DIR"] = str(output_dir)
            env["VERSION"] = "v5.1.0"

            res = subprocess.run(
                [str(_build_script)],
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(res.returncode, 0, f"Script build thất bại:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}")

            expected_deb = output_dir / "scrcpy-gui_5.1.0_amd64.deb"
            self.assertTrue(expected_deb.is_file(), f"Không tìm thấy file .deb tại: {expected_deb}")

            # 1. Kiểm tra danh sách file và quyền bằng dpkg-deb -c
            c_res = subprocess.run(
                ["dpkg-deb", "-c", str(expected_deb)],
                capture_output=True,
                text=True,
                check=True,
            )
            entries = {}
            for line in c_res.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 6:
                    perms = parts[0]
                    owner = parts[1]
                    p = parts[-1]
                    norm_path = p[1:] if p.startswith(".") else p
                    entries[norm_path] = {"perms": perms, "owner": owner}

            # Kiểm tra tất cả đều thuộc owner root/root
            for p, info in entries.items():
                self.assertEqual(info["owner"], "root/root", f"File {p} không thuộc root/root: {info['owner']}")

            # Kiểm tra các file và thư mục bắt buộc cùng quyền
            expected_files = {
                "/opt/scrcpy-gui/scrcpy": "-rwxr-xr-x",
                "/opt/scrcpy-gui/adb": "-rwxr-xr-x",
                "/opt/scrcpy-gui/scrcpy-server": "-rw-r--r--",
                "/opt/scrcpy-gui/scrcpy.png": "-rw-r--r--",
                "/opt/scrcpy-gui/disconnected.png": "-rw-r--r--",
                "/opt/scrcpy-gui/scrcpy.1": "-rw-r--r--",
                "/opt/scrcpy-gui/LICENSE": "-rw-r--r--",
                "/opt/scrcpy-gui/scrcpy_gui/__init__.py": "-rw-r--r--",
                "/opt/scrcpy-gui/scrcpy_gui/app.py": "-rw-r--r--",
                "/usr/bin/scrcpy": "-rwxr-xr-x",
                "/usr/bin/scrcpy-gui": "-rwxr-xr-x",
                "/usr/share/applications/scrcpy-gui.desktop": "-rw-r--r--",
                "/usr/share/icons/hicolor/256x256/apps/scrcpy-gui.png": "-rw-r--r--",
                "/usr/share/icons/hicolor/256x256/apps/scrcpy-screen.png": "-rw-r--r--",
                "/usr/share/applications/scrcpy-screen.desktop": "-rw-r--r--",
            }
            for path, expected_perm in expected_files.items():
                self.assertIn(path, entries, f"Thiếu file {path} trong gói deb")
                self.assertEqual(
                    entries[path]["perms"],
                    expected_perm,
                    f"Quyền của {path} không đúng: thực tế {entries[path]['perms']}, mong đợi {expected_perm}",
                )

            # 1b. Icon app và icon cửa sổ màn hình lấy từ gui/scrcpy_gui/assets
            extract_dir = tmp_path / "extract"
            subprocess.run(["dpkg-deb", "-x", str(expected_deb), str(extract_dir)], check=True)
            assets = _repo_root / "gui" / "scrcpy_gui" / "assets"
            self.assertEqual(
                (extract_dir / "usr/share/icons/hicolor/256x256/apps/scrcpy-gui.png").read_bytes(),
                (assets / "app-icon.png").read_bytes(),
            )
            self.assertEqual(
                (extract_dir / "opt/scrcpy-gui/scrcpy.png").read_bytes(),
                (assets / "screen-icon.png").read_bytes(),
            )

            self.assertEqual(
                (extract_dir / "usr/share/icons/hicolor/256x256/apps/scrcpy-screen.png").read_bytes(),
                (assets / "screen-icon.png").read_bytes(),
            )
            screen_desktop = (extract_dir / "usr/share/applications/scrcpy-screen.desktop").read_text()
            self.assertIn("StartupWMClass=scrcpy\n", screen_desktop)
            self.assertIn("Icon=scrcpy-screen\n", screen_desktop)
            self.assertIn("NoDisplay=true\n", screen_desktop)

            # 2. Kiểm tra control fields bằng dpkg-deb -f
            f_res = subprocess.run(
                ["dpkg-deb", "-f", str(expected_deb)],
                capture_output=True,
                text=True,
                check=True,
            )
            control_fields = {}
            for line in f_res.stdout.splitlines():
                if ":" in line and not line.startswith(" "):
                    k, v = line.split(":", 1)
                    control_fields[k.strip()] = v.strip()

            self.assertEqual(control_fields.get("Package"), "scrcpy-gui")
            self.assertEqual(control_fields.get("Version"), "5.1.0")
            self.assertEqual(control_fields.get("Architecture"), "amd64")
            self.assertEqual(control_fields.get("Depends"), "python3 (>= 3.10), python3-tk")
            self.assertEqual(control_fields.get("Recommends"), "va-driver-all")
            self.assertEqual(control_fields.get("Conflicts"), "scrcpy")
            self.assertEqual(control_fields.get("Replaces"), "scrcpy")
            self.assertTrue(control_fields.get("Maintainer"), "Thiếu Maintainer trong DEBIAN/control")

            # 3. Trích xuất gói và kiểm tra nội dung file chi tiết
            extract_dir = tmp_path / "extracted"
            subprocess.run(
                ["dpkg-deb", "-x", str(expected_deb), str(extract_dir)],
                check=True,
                timeout=30,
            )

            # Kiểm tra .desktop
            desktop_file = extract_dir / "usr/share/applications/scrcpy-gui.desktop"
            self.assertTrue(desktop_file.is_file())
            desktop_content = desktop_file.read_text(encoding="utf-8")
            self.assertIn("Name=Scrcpy GUI", desktop_content)
            self.assertIn("Name[vi]=Hiển thị màn hình Android", desktop_content)
            self.assertIn("Categories=Utility;", desktop_content)
            self.assertIn("Icon=scrcpy-gui", desktop_content)
            self.assertIn("StartupWMClass=scrcpy-gui", desktop_content)
            self.assertIn("Exec=scrcpy-gui", desktop_content)

            if self.has_desktop_validate:
                val_res = subprocess.run(
                    ["desktop-file-validate", str(desktop_file)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(val_res.returncode, 0, f"desktop-file-validate thất bại: {val_res.stderr}")

            # Kiểm tra wrapper /usr/bin/scrcpy-gui
            gui_wrapper = extract_dir / "usr/bin/scrcpy-gui"
            self.assertTrue(gui_wrapper.is_file())
            gui_content = gui_wrapper.read_text(encoding="utf-8")
            self.assertIn("SCRCPY_SERVER_PATH=/opt/scrcpy-gui/scrcpy-server", gui_content)
            self.assertIn("SCRCPY_BIN=/opt/scrcpy-gui/scrcpy", gui_content)
            self.assertIn("ADB=/opt/scrcpy-gui/adb", gui_content)
            self.assertIn("PYTHONPATH=/opt/scrcpy-gui", gui_content)
            self.assertIn("exec python3 -m scrcpy_gui", gui_content)

            # Kiểm tra wrapper /usr/bin/scrcpy
            scrcpy_wrapper = extract_dir / "usr/bin/scrcpy"
            self.assertTrue(scrcpy_wrapper.is_file())
            scrcpy_content = scrcpy_wrapper.read_text(encoding="utf-8")
            self.assertIn("SCRCPY_SERVER_PATH=/opt/scrcpy-gui/scrcpy-server", scrcpy_content)
            self.assertIn("ADB=/opt/scrcpy-gui/adb", scrcpy_content)
            self.assertIn("/opt/scrcpy-gui/scrcpy \"$@\"", scrcpy_content)

    def test_version_normalization(self):
        """Kiểm tra chuẩn hoá định dạng Version cho gói .deb bao gồm cả nhánh hash/chữ (0.0+...)."""
        if not self.has_dpkg_deb:
            self.skipTest("dpkg-deb không có sẵn trên hệ thống")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            dist_dir = tmp_path / "dist"
            dist_dir.mkdir()
            output_dir = tmp_path / "output"
            output_dir.mkdir()

            scrcpy_bin = dist_dir / "scrcpy"
            scrcpy_bin.write_text("#!/bin/sh\nexit 0")
            scrcpy_bin.chmod(0o755)

            adb_bin = dist_dir / "adb"
            adb_bin.write_text("#!/bin/sh\nexit 0")
            adb_bin.chmod(0o755)

            server_file = tmp_path / "scrcpy-server"
            server_file.write_text("server")

            base_env = os.environ.copy()
            base_env["DIST_DIR"] = str(dist_dir)
            base_env["SERVER_PATH"] = str(server_file)
            base_env["OUTPUT_DIR"] = str(output_dir)

            test_cases = [
                ("v2.4_beta-1", "2.4.beta-1"),
                ("deadbeef", "0.0+deadbeef"),  # Bắt đầu bằng chữ cái -> thêm tiền tố 0.0+
                ("v-git_hash", "0.0+-git.hash"),  # Bỏ 'v', bắt đầu bằng ký tự không phải số -> 0.0+
            ]

            for raw_ver, expected_ver in test_cases:
                env = base_env.copy()
                env["VERSION"] = raw_ver
                res = subprocess.run(
                    [str(_build_script)],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                self.assertEqual(res.returncode, 0, f"Build thất bại cho phiên bản {raw_ver}: {res.stderr}")

                deb_path = output_dir / f"scrcpy-gui_{expected_ver}_amd64.deb"
                self.assertTrue(deb_path.is_file(), f"Không tìm thấy deb file: {deb_path}")

                f_res = subprocess.run(
                    ["dpkg-deb", "-f", str(deb_path), "Version"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                self.assertEqual(f_res.stdout.strip(), expected_ver)

    def test_default_version_from_git_describe(self):
        """Kiểm tra khi không đặt VERSION thì script tự lấy và chuẩn hoá từ git describe."""
        if not self.has_dpkg_deb:
            self.skipTest("dpkg-deb không có sẵn trên hệ thống")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            dist_dir = tmp_path / "dist"
            dist_dir.mkdir()
            output_dir = tmp_path / "output"
            output_dir.mkdir()

            scrcpy_bin = dist_dir / "scrcpy"
            scrcpy_bin.write_text("#!/bin/sh\nexit 0")
            scrcpy_bin.chmod(0o755)

            adb_bin = dist_dir / "adb"
            adb_bin.write_text("#!/bin/sh\nexit 0")
            adb_bin.chmod(0o755)

            server_file = tmp_path / "scrcpy-server"
            server_file.write_text("server")

            env = os.environ.copy()
            env["DIST_DIR"] = str(dist_dir)
            env["SERVER_PATH"] = str(server_file)
            env["OUTPUT_DIR"] = str(output_dir)
            env.pop("VERSION", None)

            # Lấy output git describe thực tế từ repo
            git_out = subprocess.run(
                ["git", "describe", "--tags", "--always"],
                cwd=str(_repo_root),
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            expected_ver = git_out.lstrip("vV").replace("_", ".")
            expected_ver = "".join(c if (c.isalnum() or c in ".+~-") else "." for c in expected_ver)
            if not (expected_ver and expected_ver[0].isdigit()):
                expected_ver = f"0.0+{expected_ver}"

            res = subprocess.run(
                [str(_build_script)],
                cwd=str(tmp_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(res.returncode, 0, f"Build thất bại: {res.stderr}")

            deb_path = output_dir / f"scrcpy-gui_{expected_ver}_amd64.deb"
            self.assertTrue(deb_path.is_file(), f"Không tìm thấy deb file: {deb_path}")

            f_res = subprocess.run(
                ["dpkg-deb", "-f", str(deb_path), "Version"],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(f_res.stdout.strip(), expected_ver)

    def test_relative_paths(self):
        """Kiểm tra chạy script với đường dẫn tương đối cho DIST_DIR, SERVER_PATH, OUTPUT_DIR từ thư mục bất kỳ."""
        if not self.has_dpkg_deb:
            self.skipTest("dpkg-deb không có sẵn trên hệ thống")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            dist_dir = tmp_path / "rel_dist"
            dist_dir.mkdir()
            output_dir = tmp_path / "rel_out"
            output_dir.mkdir()

            scrcpy_bin = dist_dir / "scrcpy"
            scrcpy_bin.write_text("#!/bin/sh\nexit 0")
            scrcpy_bin.chmod(0o755)

            adb_bin = dist_dir / "adb"
            adb_bin.write_text("#!/bin/sh\nexit 0")
            adb_bin.chmod(0o755)

            server_file = tmp_path / "rel_server"
            server_file.write_text("server")

            env = os.environ.copy()
            # Dùng đường dẫn tương đối so với cwd (tmp_path)
            env["DIST_DIR"] = "./rel_dist"
            env["SERVER_PATH"] = "./rel_server"
            env["OUTPUT_DIR"] = "./rel_out"
            env["VERSION"] = "3.0.0"

            res = subprocess.run(
                [str(_build_script)],
                cwd=str(tmp_path),
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(res.returncode, 0, f"Build thất bại với đường dẫn tương đối: {res.stderr}")

            deb_path = output_dir / "scrcpy-gui_3.0.0_amd64.deb"
            self.assertTrue(deb_path.is_file(), f"File deb không tồn tại: {deb_path}")



if __name__ == "__main__":
    unittest.main()
