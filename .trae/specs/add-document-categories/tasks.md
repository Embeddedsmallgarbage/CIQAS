# Tasks

- [x] Task 1: 修改后端支持文档分类
  - [x] SubTask 1.1: 在 build_db.py 中添加分类元数据支持
  - [x] SubTask 1.2: 修改 process_documents 方法接收 category 参数
  - [x] SubTask 1.3: 添加 list_documents_by_category 方法
  - [x] SubTask 1.4: 添加预设分类常量

- [x] Task 2: 修改上传 API
  - [x] SubTask 2.1: 修改 app.py 上传接口接收 category 参数
  - [x] SubTask 2.2: 添加获取分类列表 API
  - [x] SubTask 2.3: 修改文档列表 API 返回分类结构

- [x] Task 3: 更新前端上传界面
  - [x] SubTask 3.1: 在上传区域添加分类下拉选择框
  - [x] SubTask 3.2: 更新 handleFiles 函数传递分类参数
  - [x] SubTask 3.3: 添加分类选择样式

- [x] Task 4: 实现文件夹树形展示
  - [x] SubTask 4.1: 创建文件夹组件 HTML 结构
  - [x] SubTask 4.1: 添加文件夹展开/折叠 CSS 样式
  - [x] SubTask 4.2: 实现 renderDocumentTree JavaScript 函数
  - [x] SubTask 4.3: 添加文件夹点击展开/折叠交互

- [x] Task 5: 添加分类图标
  - [x] SubTask 5.1: 为每个分类添加对应的 SVG 图标
  - [x] SubTask 5.2: 添加空文件夹状态显示

# Task Dependencies
- [Task 2] depends on [Task 1]
- [Task 3] depends on [Task 2]
- [Task 4] depends on [Task 2]
- [Task 5] depends on [Task 4]
