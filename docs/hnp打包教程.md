# 1. 复制后端代码到 HNP 目录
Copy-Item "D:\WorkSpace\zungen\finance-agent\apps\python\src\finance_agent_backend" `
  "D:\HarmonyDevelopment\finance_agent_hnp\lib\python3.13\site-packages\" `
  -Recurse -Force

# 2. 重新打包
Remove-Item "D:\HarmonyDevelopment\output\finance-agent-backend.hnp" -ErrorAction SilentlyContinue

& "D:\Development\DevEco Studio\sdk\default\openharmony\toolchains\hnpcli.exe" `
  pack -i "D:\HarmonyDevelopment\finance_agent_hnp" -o "D:\HarmonyDevelopment\output"


