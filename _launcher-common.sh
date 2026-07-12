# Shared launcher boilerplate — sourced by run-mac-watchdog.sh and
# run-statusbar.sh. Sets PYTHONPATH, activates a local .venv if present,
# and exports PYTHON_BIN. Expects DIR to be set to the repo root.

export PYTHONPATH="${DIR}/src:${PYTHONPATH:-}"

# If a local virtualenv exists, activate it (so pip-installed packages are used)
VENV_DIR="${DIR}/.venv"
if [ -d "${VENV_DIR}" ]; then
  if [ -f "${VENV_DIR}/bin/activate" ]; then
    # shellcheck disable=SC1090
    . "${VENV_DIR}/bin/activate"
  fi
  # Ensure venv bin is first on PATH (covers cases where activate wasn't sourced)
  export PATH="${VENV_DIR}/bin:${PATH}"
fi

# Prefer python from PATH (venv will supply one if activated) or fall back
PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "${PYTHON_BIN}" ]; then
  echo "Python not found. Please install Python 3 or create a .venv." >&2
  exit 1
fi
