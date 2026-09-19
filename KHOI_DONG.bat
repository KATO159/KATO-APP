@echo off
chcp 65001 >/dev/null 2>&1
title KATO - Quan Ly Thue Do
cd /d "%~dp0"

echo.
echo  ============================================
echo    KATO - UNG DUNG QUAN LY THUE DO
echo  ============================================
echo.

REM ---------- Buoc 1: kiem tra Python ----------
python --version >/dev/null 2>&1
if errorlevel 1 (
  echo  [DUNG LAI] May tinh chua cai Python.
  echo.
  echo  Tai tai day:  https://www.python.org/downloads/
  echo  QUAN TRONG: o man hinh cai dat dau tien, nho TICH O
  echo               "Add python.exe to PATH" roi moi bam Install.
  echo.
  echo  Cai xong thi dong cua so nay va bam dup lai file nay.
  echo.
  pause
  exit /b 1
)

REM ---------- Buoc 2: tai ma nguon neu chua co ----------
if exist "app_thue_do.py" goto cai_thu_vien

git --version >/dev/null 2>&1
if errorlevel 1 (
  echo  [DUNG LAI] May tinh chua cai Git.
  echo.
  echo  Tai tai day:  https://git-scm.com/download/win
  echo  Bam Next den het la duoc, khong can doi gi.
  echo.
  echo  Cai xong thi dong cua so nay va bam dup lai file nay.
  echo.
  pause
  exit /b 1
)

echo  [1/3] Dang tai ma nguon tu GitHub...
if not exist ".git" (
  git init -q
  git remote add origin https://github.com/KATO159/KATO-APP.git
)
git fetch --depth 1 origin claude/app-quan-ly-thue-do-ec0br7
if errorlevel 1 (
  echo  [LOI] Khong tai duoc ma nguon. Kiem tra ket noi mang roi thu lai.
  pause
  exit /b 1
)
git checkout -B kato-app FETCH_HEAD
if errorlevel 1 (
  echo  [LOI] Khong ghi duoc ma nguon vao thu muc nay.
  echo  Hay tao mot thu muc moi rong, chep file nay vao do va chay lai.
  pause
  exit /b 1
)
goto cai_thu_vien

:cai_thu_vien
REM ---------- Buoc 3: cai thu vien ----------
echo  [2/3] Dang kiem tra thu vien...
python -c "import streamlit" >/dev/null 2>&1
if errorlevel 1 (
  echo        Chua co, dang cai dat. Buoc nay mat vai phut, vui long cho...
  python -m pip install --quiet --upgrade pip
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo  [LOI] Cai thu vien that bai. Chup man hinh doan chu do o tren va gui lai.
    pause
    exit /b 1
  )
) else (
  echo        Thu vien da day du.
)

REM ---------- Buoc 4: chay ----------
echo  [3/3] Dang khoi dong ung dung...
echo.
echo  Trinh duyet se tu mo sau vai giay.
echo  Neu khong tu mo, go dia chi nay vao trinh duyet:  http://localhost:8501
echo.
echo  MUON TAT UNG DUNG: bam Ctrl + C tai cua so nay, hoac dong cua so.
echo.
python -m streamlit run app_thue_do.py

echo.
echo  Ung dung da dung.
pause
