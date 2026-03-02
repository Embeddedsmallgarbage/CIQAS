# Tasks

- [x] Task 1: 修改侧边栏按钮
  - [x] SubTask 1.1: 将「知识库管理」按钮改为「设置」按钮
  - [x] SubTask 1.2: 设置按钮对所有登录用户可见
  - [x] SubTask 1.3: 更新按钮图标为设置图标

- [x] Task 2: 创建设置界面 UI
  - [x] SubTask 2.1: 创建设置模态框结构
  - [x] SubTask 2.2: 添加左侧导航栏
  - [x] SubTask 2.3: 添加右侧内容区
  - [x] SubTask 2.4: 实现标签页切换逻辑

- [x] Task 3: 迁移知识库管理功能
  - [x] SubTask 3.1: 将知识库管理内容迁移到设置界面
  - [x] SubTask 3.2: 更新相关 JavaScript 函数

- [x] Task 4: 实现学生账号管理
  - [x] SubTask 4.1: 在 auth.py 中添加学生账号管理方法
  - [x] SubTask 4.2: 创建学生账号列表 UI
  - [x] SubTask 4.3: 创建添加学生账号表单
  - [x] SubTask 4.4: 实现删除学生账号功能

- [x] Task 5: 添加后端 API
  - [x] SubTask 5.1: 添加获取学生列表 API
  - [x] SubTask 5.2: 添加创建学生账号 API
  - [x] SubTask 5.3: 添加删除学生账号 API

- [x] Task 6: 权限控制
  - [x] SubTask 6.1: 学生用户隐藏知识库管理和学生账号管理
  - [x] SubTask 6.2: 学生用户仅显示通用设置（如有）

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 2]
- [Task 4] depends on [Task 2]
- [Task 5] depends on [Task 4]
- [Task 6] depends on [Task 2, Task 3, Task 4]
