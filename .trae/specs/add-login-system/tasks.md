# Tasks

- [x] Task 1: 创建用户认证模块 (auth.py)
  - [x] SubTask 1.1: 实现用户数据结构（管理员/学生角色）
  - [x] SubTask 1.2: 实现密码哈希验证
  - [x] SubTask 1.3: 实现 session 管理
  - [x] SubTask 1.4: 实现登录/登出逻辑
  - [x] SubTask 1.5: 实现权限装饰器（login_required, admin_required）

- [x] Task 2: 创建登录页面 UI
  - [x] SubTask 2.1: 使用 ui-ux-pro-max 生成设计系统
  - [x] SubTask 2.2: 创建 login.html 模板
  - [x] SubTask 2.3: 添加登录页面 CSS 样式
  - [x] SubTask 2.4: 实现登录表单交互

- [x] Task 3: 修改后端路由
  - [x] SubTask 3.1: 添加 /login GET/POST 路由
  - [x] SubTask 3.2: 添加 /logout 路由
  - [x] SubTask 3.3: 添加认证中间件保护路由
  - [x] SubTask 3.4: 添加用户信息 API 端点

- [x] Task 4: 修改前端页面
  - [x] SubTask 4.1: 在主页面添加用户信息显示
  - [x] SubTask 4.2: 添加登出按钮
  - [x] SubTask 4.3: 根据用户角色显示/隐藏知识库管理按钮
  - [x] SubTask 4.4: 添加未登录重定向逻辑

- [x] Task 5: 内置管理员账号
  - [x] SubTask 5.1: 在数据库或配置中添加默认管理员账号

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 1]
- [Task 4] depends on [Task 1, Task 3]
- [Task 5] depends on [Task 1]
