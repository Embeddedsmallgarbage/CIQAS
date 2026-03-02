# 用户登录系统 Spec

## Why
当前系统没有用户认证机制，任何人都可以访问所有功能包括知识库管理。需要增加登录系统来区分管理员和学生用户，保护敏感的管理功能。

## What Changes
- 新增登录页面，支持管理员和学生两种角色登录
- 新增用户认证模块（auth.py）
- 新增 session 管理和权限控制
- 修改前端页面，根据用户角色显示/隐藏功能
- 新增登出功能
- 内置管理员账号

## Impact
- Affected code: app.py, templates/index.html, static/js/main.js, static/css/style.css
- New files: auth.py, templates/login.html

## ADDED Requirements

### Requirement: 登录页面
系统应提供专业的登录页面，用户必须先登录才能访问问答系统。

#### Scenario: 访问登录页面
- **WHEN** 用户首次访问网站
- **THEN** 显示登录页面，包含账号密码输入框和登录按钮

#### Scenario: 登录页面设计
- **WHEN** 用户查看登录页面
- **THEN** 页面采用与主系统一致的学术风格设计
- **AND** 包含系统名称和简介
- **AND** 包含账号和密码输入框
- **AND** 包含登录按钮
- **AND** 输入框有适当的标签和占位符

### Requirement: 用户认证
系统应验证用户身份并区分角色。

#### Scenario: 管理员登录成功
- **WHEN** 用户输入正确的管理员账号和密码
- **THEN** 登录成功，跳转到主页面
- **AND** 可以访问所有功能包括知识库管理

#### Scenario: 学生登录成功
- **WHEN** 用户输入正确的学生账号和密码
- **THEN** 登录成功，跳转到主页面
- **AND** 只能使用问答功能
- **AND** 知识库管理按钮不可见或禁用

#### Scenario: 登录失败
- **WHEN** 用户输入错误的账号或密码
- **THEN** 显示错误提示"账号或密码错误"
- **AND** 保留在登录页面

### Requirement: 权限控制
系统应根据用户角色控制功能访问。

#### Scenario: 管理员权限
- **WHEN** 管理员登录后
- **THEN** 可以使用问答系统
- **AND** 可以打开知识库管理面板
- **AND** 可以上传、删除文档

#### Scenario: 学生权限
- **WHEN** 学生登录后
- **THEN** 可以使用问答系统
- **AND** 知识库管理按钮不显示

#### Scenario: 未登录访问
- **WHEN** 未登录用户尝试访问主页面
- **THEN** 重定向到登录页面

### Requirement: 会话管理
系统应管理用户会话状态。

#### Scenario: 会话保持
- **WHEN** 用户登录成功
- **THEN** 创建会话，保持登录状态
- **AND** 会话有效期默认 24 小时

#### Scenario: 登出
- **WHEN** 用户点击登出按钮
- **THEN** 清除会话
- **AND** 重定向到登录页面

### Requirement: 内置账号
系统应包含预设的管理员账号。

#### Scenario: 管理员账号
- **GIVEN** 系统内置管理员账号
- **WHEN** 使用账号 202203010104 和密码 123456 登录
- **THEN** 以管理员身份登录成功

### Requirement: 登录页面 UI/UX
登录页面应遵循专业 UI 设计规范。

#### Scenario: 设计规范
- **WHEN** 渲染登录页面
- **THEN** 使用与主系统一致的配色方案（学术风象牙色调）
- **AND** 使用 DM Sans + Noto Serif SC 字体
- **AND** 所有按钮最小高度 44px
- **AND** 所有交互元素有 focus-visible 状态
- **AND** 表单有正确的 label 关联
- **AND** 使用 SVG 图标而非 emoji
