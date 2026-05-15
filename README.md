<p align="center">
  <a href="#">
    <img alt="Catixs FinWork Logo" width="200" src="./deploy/sample-picture/logo.svg">
  </a>
</p>

<h1 align="center">Catixs FinWork</h1>

English | [简体中文](./README.md)

Catixs FinWork is an internal finance and operations platform built with FastAPI, Vue3, and Naive UI. It includes RBAC permission management, dynamic routing, JWT authentication, ticket workflows, vendor management, asset management, and PostgreSQL-backed business data.

### Features
- **Popular Tech Stack**: The backend is developed with the high-performance asynchronous framework FastAPI using Python 3.13, while the front-end is powered by Vue3 and Vite, with pnpm for package management.
- **Code Standards**: The project is equipped with various plugins for code standardization and quality control, ensuring consistency and enhancing team collaboration efficiency.
- **Dynamic Routing**: Backend dynamic routing combined with the RBAC model allows for fine-grained control of menus and routing.
- **JWT Authentication**: User identity verification and authorization are handled through JWT, enhancing the application's security.
- **Granular Permission Control**: Implements detailed permission management including button and interface level controls, ensuring different roles and users have appropriate permissions.

### Default Account

The application creates a default superuser during first startup if the user table is empty.

- Username: admin
- Password: Catixs@3202

### Screenshots

#### Login Page
![Login Page](./deploy/sample-picture/login.jpg)

#### Workbench
![Workbench](./deploy/sample-picture/workbench.jpg)

#### User Management
![User Management](./deploy/sample-picture/user.jpg)

#### Role Management
![Role Management](./deploy/sample-picture/role.jpg)

#### Menu Management
![Menu Management](./deploy/sample-picture/menu.jpg)

#### API Management
![API Management](./deploy/sample-picture/api.jpg)

### Installation

Catixs FinWork is a FastAPI + Vue application. The production build is served by FastAPI directly: API routes are mounted under `/api`, frontend static files are served from `web/dist`, and uploaded files are served from `/uploads`.

#### Requirements

- Python 3.13
- Node.js 20
- pnpm
- PostgreSQL

#### Environment Variables

Create `.env` locally, or configure the same variables in your deployment platform:

```sh
DB_TYPE=postgres
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_DATABASE=finwork
POSTGRES_SSL=false
```

If your PostgreSQL server requires SSL, set `POSTGRES_SSL=true`. If the server rejects SSL upgrade, keep it as `false`.

You can also use a single DSN. `POSTGRES_DSN` takes precedence over the individual `POSTGRES_*` fields:

```sh
DB_TYPE=postgres
POSTGRES_DSN=postgres://postgres:your_password@127.0.0.1:5432/finwork
```

#### Local Development

Install `uv` and backend dependencies:

```sh
python -m pip install uv
uv sync --no-install-project
```

If your Python command is `python3`:

```sh
python3 -m pip install uv
uv sync --no-install-project
```

Install frontend dependencies:

```sh
cd web
pnpm install
```

Start development servers in two terminals:

```sh
uv run python run.py
```

```sh
cd web
pnpm dev
```

The backend API documentation is available at:

```text
http://localhost:9999/docs
```

#### Production Build

Build the frontend first:

```sh
cd web
pnpm install --frozen-lockfile
pnpm run build
cd ..
```

Create runtime directories:

```sh
mkdir -p migrations uploads/tickets app/logs
```

Start the application:

```sh
UVICORN_RELOAD=false PORT=8000 uv run python run.py
```

The application will serve both the frontend and backend from the same port.

#### Nixpacks Deployment

For Coolify or other Nixpacks-based platforms, select:

```text
Build Pack: Nixpacks
```

The repository includes `nixpacks.toml`, which performs these steps:

```text
1. install Python 3.13, uv, Node.js 20, pnpm, gcc
2. install backend dependencies with `uv sync --no-dev --no-install-project`
3. install frontend dependencies with pnpm
4. build web/dist
5. start the app with `uv run python run.py`
```

Configure the PostgreSQL environment variables in the platform UI. Do not bake `.env` into the deployment image.

#### Database Initialization

On startup, the backend runs database initialization and migrations through Aerich/Tortoise. Make sure the configured PostgreSQL database exists before starting the app.

If the database does not exist yet and you want the helper script to create it:

```sh
python scripts/migrate_sqlite_to_postgres.py --create-database-only
```

SQLite import is optional and only needed when moving old local data into PostgreSQL:

```sh
python scripts/migrate_sqlite_to_postgres.py
```

If the target PostgreSQL tables already contain data and you intentionally want to replace them:

```sh
python scripts/migrate_sqlite_to_postgres.py --truncate
```

#### Docker

Docker is optional. The current recommended deployment path is Nixpacks. If Docker is used, pass database configuration at runtime with environment variables; do not copy `.env` into the image.

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

