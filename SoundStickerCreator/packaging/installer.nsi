Unicode true
Name "Sound Sticker Creator"
OutFile "${OUTPUT}"
InstallDir "$LOCALAPPDATA\Programs\Sound Sticker Creator"
RequestExecutionLevel user
SetCompressor /SOLID lzma
!include "MUI2.nsh"
!include "x64.nsh"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Spanish"
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Se requiere Windows de 64 bits."
    Abort
  ${EndIf}
FunctionEnd

Section
  SetOutPath "$INSTDIR"
  File /r "${STAGE}/*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Sound Sticker Creator"
  CreateShortcut "$SMPROGRAMS\Sound Sticker Creator\Sound Sticker Creator.lnk" "$INSTDIR\Sound Sticker Creator.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SoundStickerCreator" "DisplayName" "Sound Sticker Creator"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SoundStickerCreator" "DisplayVersion" "0.1.0"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SoundStickerCreator" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\Sound Sticker Creator\Sound Sticker Creator.lnk"
  RMDir "$SMPROGRAMS\Sound Sticker Creator"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\SoundStickerCreator"
  Delete "$INSTDIR\Sound Sticker Creator.exe"
  Delete "$INSTDIR\Uninstall.exe"
  Delete "$INSTDIR\app.py"
  Delete "$INSTDIR\desktop.py"
  Delete "$INSTDIR\media.py"
  Delete "$INSTDIR\riff.py"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\THIRD_PARTY_NOTICES.md"
  Delete "$INSTDIR\tools\node.exe"
  Delete "$INSTDIR\tools\NODE-LICENSE"
  Delete "$INSTDIR\tools\GO-LICENSE"
  RMDir "$INSTDIR\tools"
  RMDir /r "$INSTDIR\docs"
  RMDir /r "$INSTDIR\runtime"
  RMDir /r "$INSTDIR\transport"
  RMDir "$INSTDIR"
SectionEnd
