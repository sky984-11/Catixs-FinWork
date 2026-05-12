<p align="center">
  <a href="https://github.com/mizhexiaoxiao/vue-fastapi-admin">
    <img alt="Vue FastAPI Admin Logo" width="200" src="https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/logo.svg">
  </a>
</p>

<h1 align="center">vue-fastapi-admin</h1>

English | [简体中文](./README.md)

vue-fastapi-admin is a modern front-end and back-end separation development platform that combines FastAPI, Vue3, and Naive UI. It incorporates RBAC (Role-Based Access Control) management, dynamic routing, and JWT (JSON Web Token) authentication, making it ideal for rapid development of small to medium-sized applications and also serves as a valuable learning resource.

### Features
- **Popular Tech Stack**: The backend is developed with the high-performance asynchronous framework FastAPI using Python 3.11, while the front-end is powered by cutting-edge technologies such as Vue3 and Vite, complemented by the efficient package manager, pnpm.
- **Code Standards**: The project is equipped with various plugins for code standardization and quality control, ensuring consistency and enhancing team collaboration efficiency.
- **Dynamic Routing**: Backend dynamic routing combined with the RBAC model allows for fine-grained control of menus and routing.
- **JWT Authentication**: User identity verification and authorization are handled through JWT, enhancing the application's security.
- **Granular Permission Control**: Implements detailed permission management including button and interface level controls, ensuring different roles and users have appropriate permissions.

### Live Demo
- URL: http://139.9.100.77:9999
- Username: admin
- Password: 123456

### Screenshots

#### Login Page
![Login Page](https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/login.jpg)

#### Workbench
![Workbench](https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/workbench.jpg)

#### User Management
![User Management](https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/user.jpg)

#### Role Management
![Role Management](https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/role.jpg)

#### Menu Management
![Menu Management](https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/menu.jpg)

#### API Management
![API Management](https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/api.jpg)

### Quick Start
Please follow the instructions below for installation and configuration:

#### Method 1：dockerhub pull image

```sh
docker pull mizhexiaoxiao/vue-fastapi-admin:latest 
docker run -d --restart=always --name=vue-fastapi-admin -p 9999:80 mizhexiaoxiao/vue-fastapi-admin
```

#### Method 2: Build Image Using Dockerfile
##### Install Docker

```sh
yum install -y docker-ce
systemctl start docker
```

##### Build the Image

```sh
git clone https://github.com/mizhexiaoxiao/vue-fastapi-admin.git
cd vue-fastapi-admin
docker build --no-cache . -t vue-fastapi-admin
```

##### Start the Container

```sh
docker run -d --restart=always --name=vue-fastapi-admin -p 9999:80 vue-fastapi-admin
```

##### Access the Service

http://localhost:9999

username：admin

password：123456

### Local Setup
#### Backend
The backend service requires the following environment:
- Python 3.11

#### Method 1 (Recommended): Install Dependencies with uv
1. Install uv
```sh
pip install uv
```

2. Create and activate virtual environment
```sh
uv venv
source .venv/bin/activate  # Linux/Mac
# or
.\.venv\Scripts\activate  # Windows
```

3. Install dependencies
```sh
uv sync
```

4. Start the backend service
```sh
python run.py
```

#### Method 2: Install Dependencies with Pip
1. Create a Python virtual environment:
```sh
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate  # Windows
```

2. Install project dependencies:
```sh
pip install -r requirements.txt
```

3. Start the backend service:
```sh
uv run python run.py
```
The backend service is now running, and you can visit http://localhost:9999/docs to view the API documentation.

#### Frontend
The frontend project requires a Node.js environment (recommended version 18.8.0 or higher).
- node v18.8.0+

1. Navigate to the frontend project directory:
```sh
cd web
```

2. Install project dependencies (pnpm is recommended: https://pnpm.io/zh/installation)
```sh
npm i -g pnpm # If pnpm is already installed, skip this step
pnpm i # Or use npm i
```

3. Start the frontend development server:
```sh
pnpm dev
```

### Directory Structure Explanation

```
├── app                   // 应用程序目录
│   ├── api               // API接口目录
│   │   └── v1            // 版本1的API接口
│   │       ├── apis      // API相关接口
│   │       ├── base      // 基础信息接口
│   │       ├── menus     // 菜单相关接口
│   │       ├── roles     // 角色相关接口
│   │       └── users     // 用户相关接口
│   ├── controllers       // 控制器目录
│   ├── core              // 核心功能模块
│   ├── log               // 日志目录
│   ├── models            // 数据模型目录
│   ├── schemas           // 数据模式/结构定义
│   ├── settings          // 配置设置目录
│   └── utils             // 工具类目录
├── deploy                // 部署相关目录
│   └── sample-picture    // 示例图片目录
└── web                   // 前端网页目录
    ├── build             // 构建脚本和配置目录
    │   ├── config        // 构建配置
    │   ├── plugin        // 构建插件
    │   └── script        // 构建脚本
    ├── public            // 公共资源目录
    │   └── resource      // 公共资源文件
    ├── settings          // 前端项目配置
    └── src               // 源代码目录
        ├── api           // API接口定义
        ├── assets        // 静态资源目录
        │   ├── images    // 图片资源
        │   ├── js        // JavaScript文件
        │   └── svg       // SVG矢量图文件
        ├── components    // 组件目录
        │   ├── common    // 通用组件
        │   ├── icon      // 图标组件
        │   ├── page      // 页面组件
        │   ├── query-bar // 查询栏组件
        │   └── table     // 表格组件
        ├── composables   // 可组合式功能块
        ├── directives    // 指令目录
        ├── layout        // 布局目录
        │   └── components // 布局组件
        ├── router        // 路由目录
        │   ├── guard     // 路由守卫
        │   └── routes    // 路由定义
        ├── store         // 状态管理(pinia)
        │   └── modules   // 状态模块
        ├── styles        // 样式文件目录
        ├── utils         // 工具类目录
        │   ├── auth      // 认证相关工具
        │   ├── common    // 通用工具
        │   ├── http      // 封装axios
        │   └── storage   // 封装localStorage和sessionStorage
        └── views         // 视图/页面目录
            ├── error-page // 错误页面
            ├── login      // 登录页面
            ├── profile    // 个人资料页面
            ├── system     // 系统管理页面
            └── workbench  // 工作台页面
```

### Visitors Count

<img align="left" src = "https://profile-counter.glitch.me/vue-fastapi-admin/count.svg" alt="Loading">