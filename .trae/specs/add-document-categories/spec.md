# 文档分类管理功能 Spec

## Why
当前知识库管理中所有文档都平铺显示，缺乏组织结构。需要添加分类文件夹功能，让管理员可以按类别组织文档，便于管理和检索。

## What Changes
- 上传文档时增加分类选择下拉框
- 文档列表改为文件夹树形结构展示
- 添加默认分类文件夹（规章制度、办事流程、校园生活、教学管理、其他）
- 后端支持文档分类元数据存储

## Impact
- Affected code: build_db.py, app.py, templates/index.html, static/js/main.js, static/css/style.css
- New data: 文档元数据中增加 category 字段

## ADDED Requirements

### Requirement: 文档分类选择
上传文档时应提供分类选择功能。

#### Scenario: 显示分类选择
- **WHEN** 管理员打开上传区域
- **THEN** 显示分类下拉选择框
- **AND** 下拉框包含预设的分类选项

#### Scenario: 选择分类上传
- **WHEN** 管理员选择分类并上传文档
- **THEN** 文档被标记为该分类
- **AND** 文档在对应分类文件夹中显示

#### Scenario: 默认分类
- **WHEN** 管理员未选择分类直接上传
- **THEN** 文档自动归类到"其他"分类

### Requirement: 分类文件夹展示
文档列表应以文件夹形式展示。

#### Scenario: 文件夹列表显示
- **WHEN** 管理员查看知识库管理页面
- **THEN** 显示分类文件夹列表
- **AND** 每个文件夹显示名称和文档数量

#### Scenario: 展开文件夹
- **WHEN** 管理员点击文件夹
- **THEN** 展开显示该分类下的所有文档
- **AND** 再次点击可折叠

#### Scenario: 空文件夹
- **WHEN** 某分类下没有文档
- **THEN** 显示空文件夹图标
- **AND** 展开后显示"暂无文档"

### Requirement: 预设分类
系统应提供适合高校事务的预设分类。

#### Scenario: 默认分类列表
- **GIVEN** 系统初始化
- **WHEN** 用户查看分类列表
- **THEN** 显示以下分类：
  - 规章制度（校规校纪、管理制度等）
  - 办事流程（各类办事指南）
  - 校园生活（宿舍、食堂、图书馆等）
  - 教学管理（选课、考试、成绩等）
  - 其他（未分类文档）

### Requirement: 分类管理
管理员可以管理文档分类。

#### Scenario: 删除分类中的文档
- **WHEN** 管理员在展开的文件夹中点击删除按钮
- **THEN** 删除该文档
- **AND** 更新文件夹文档数量

#### Scenario: 文档数量统计
- **WHEN** 文档上传或删除后
- **THEN** 自动更新对应分类的文档数量

## MODIFIED Requirements

### Requirement: 文档上传
原有文档上传功能需要增加分类参数。

#### Scenario: 上传接口修改
- **WHEN** 调用文档上传 API
- **THEN** 接收 category 参数
- **AND** 将分类信息存入文档元数据

### Requirement: 文档列表
原有平铺文档列表改为树形文件夹结构。

#### Scenario: 列表接口修改
- **WHEN** 获取文档列表
- **THEN** 返回按分类组织的文档结构
- **AND** 包含每个分类的文档数量

## REMOVED Requirements
无
