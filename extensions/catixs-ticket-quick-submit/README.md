# Catixs 工单快捷提交 Chrome 插件

用于从浏览器工具栏快速提交 Catixs FinWork 工单。

## 功能

- 快速填写工单标题、类型、地点、描述。
- 自动带入当前网页标题和 URL。
- 支持右键页面或选中文字后“提交为 Catixs 工单”。
- 固定提交到 `https://finwork.catixs.net`。
- 用户名和密码长期保存在当前浏览器本地。
- 提交时先调用后端登录接口生成 Token，再调用工单创建接口。
- 提交成功后自动打开工单详情页。

## 安装

1. 打开 Chrome `chrome://extensions/`。
2. 开启右上角“开发者模式”。
3. 点击“加载已解压的扩展程序”。
4. 选择本目录：`extensions/catixs-ticket-quick-submit`。

## 配置

点击插件图标，在账号设置里填写 FinWork 用户名和密码。

## 接口

插件调用：

```text
POST https://finwork.catixs.net/api/v1/base/access_token
POST https://finwork.catixs.net/api/v1/ticket/create
```
