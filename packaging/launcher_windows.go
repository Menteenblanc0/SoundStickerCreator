package main

import (
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"unsafe"
)

func showError(message string) {
	box := syscall.NewLazyDLL("user32.dll").NewProc("MessageBoxW")
	text, _ := syscall.UTF16PtrFromString(message)
	title, _ := syscall.UTF16PtrFromString("Sound Sticker Creator")
	box.Call(0, uintptr(unsafe.Pointer(text)), uintptr(unsafe.Pointer(title)), 0x10)
}

func main() {
	executable, err := os.Executable()
	if err != nil {
		showError("No se pudo ubicar la carpeta de Sound Sticker Creator.")
		os.Exit(1)
	}
	base := filepath.Dir(executable)
	command := exec.Command(filepath.Join(base, "runtime", "pythonw.exe"), "-I", "-B", "-c",
		"import sys,runpy; sys.path.insert(0,sys.argv.pop(1)); runpy.run_path(sys.argv.pop(1),run_name='__main__')",
		base, filepath.Join(base, "app.py"))
	command.Dir = base
	command.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
	if err := command.Run(); err != nil {
		showError("No se pudo iniciar Sound Sticker Creator. Conserva la carpeta runtime junto al ejecutable.")
		os.Exit(1)
	}
}
