# Catixs FinWork Windows App

这是 `https://finwork.catixs.net` 的 Windows 桌面版封装。

## 开发预览

```powershell
cd desktop\finwork-windows
npm install
npm run start
```

## 打包 Windows 安装包

```powershell
cd desktop\finwork-windows
.\build.ps1
```

打包结果会输出到：

```text
desktop\finwork-windows\release
```

默认会生成安装版和绿色便携版：

```text
Catixs FinWork-1.0.0-x64-Setup.exe
Catixs FinWork-1.0.0-x64-Portable.exe
```

安装版会创建桌面快捷方式和开始菜单快捷方式，安装后可以右键任务栏图标选择固定。

## 切换访问地址

默认地址是：

```text
https://finwork.catixs.net
```

临时预览其他地址：

```powershell
$env:FINWORK_URL="https://finwork.catixs.net"
npm run start
```
