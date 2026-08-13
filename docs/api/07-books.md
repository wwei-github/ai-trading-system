# 书籍管理

> 书籍管理：书籍上传、解析、阅读进度、RAG 问答与笔记。

## 接口列表

| 方法 | 路径 | 简介 |
|---|---|---|
| `GET` | `/api/v1/books` | [获取书籍列表](#get-api-v1-books) |
| `POST` | `/api/v1/books` | [创建书籍记录](#post-api-v1-books) |
| `GET` | `/api/v1/books/health` | [健康检查](#get-api-v1-books-health) |
| `POST` | `/api/v1/books/upload` | [上传书籍文件](#post-api-v1-books-upload) |
| `DELETE` | `/api/v1/books/{book_id}` | [删除书籍](#delete-api-v1-books-book-id) |
| `GET` | `/api/v1/books/{book_id}` | [获取书籍详情](#get-api-v1-books-book-id) |
| `PATCH` | `/api/v1/books/{book_id}` | [更新书籍信息](#patch-api-v1-books-book-id) |
| `GET` | `/api/v1/books/{book_id}/notes` | [获取笔记列表](#get-api-v1-books-book-id-notes) |
| `POST` | `/api/v1/books/{book_id}/notes` | [创建笔记](#post-api-v1-books-book-id-notes) |
| `POST` | `/api/v1/books/{book_id}/parse` | [触发内容解析](#post-api-v1-books-book-id-parse) |
| `PATCH` | `/api/v1/books/{book_id}/progress` | [更新阅读进度](#patch-api-v1-books-book-id-progress) |
| `POST` | `/api/v1/books/{book_id}/qa` | [书籍 RAG 问答](#post-api-v1-books-book-id-qa) |


## GET `/api/v1/books`

**获取书籍列表**

获取当前用户的书籍列表。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## POST `/api/v1/books`

**创建书籍记录**

创建书籍记录（不包含文件上传，适用于手动录入）。

### 请求参数

_(无)_

### 请求体

- `Content-Type: application/json`
  - Schema: [BookCreate](./10-schemas.md#BookCreate)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | title | string | 是 | 书名 |
    | author | any | 否 | Author |
    | category | any | 否 | Category |
    | file_type | any | 否 | File Type |
    | cover_url | any | 否 | Cover Url |
    | file_path | any | 否 | File Path |
    | metadata | any | 否 | Metadata |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 201 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/books/health`

**健康检查**

书籍模块健康检查。

### 请求参数

_(无)_

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |


## POST `/api/v1/books/upload`

**上传书籍文件**

上传书籍文件并创建书籍记录。

支持的文件类型：pdf / epub / txt
上传后可通过 `POST /books/{book_id}/parse` 触发内容解析。

### 请求参数

_(无)_

### 请求体

- `Content-Type: multipart/form-data`
  - Schema: [Body_upload_book_api_v1_books_upload_post](./10-schemas.md#Body_upload_book_api_v1_books_upload_post)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | file | string (binary) | 是 | 书籍文件 (pdf/epub/txt) |
    | title | any | 否 | 书名（可选，默认使用文件名） |
    | author | any | 否 | 作者 |
    | category | any | 否 | 分类 |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 201 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## DELETE `/api/v1/books/{book_id}`

**删除书籍**

删除书籍（同时删除关联的笔记和知识块）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| book_id | path | string (uuid) | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/books/{book_id}`

**获取书籍详情**

获取书籍详情。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| book_id | path | string (uuid) | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## PATCH `/api/v1/books/{book_id}`

**更新书籍信息**

更新书籍信息。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| book_id | path | string (uuid) | 是 |  |

### 请求体

- `Content-Type: application/json`
  - Schema: [BookUpdate](./10-schemas.md#BookUpdate)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | title | any | 否 | Title |
    | author | any | 否 | Author |
    | category | any | 否 | Category |
    | cover_url | any | 否 | Cover Url |
    | progress | any | 否 | Progress |
    | metadata | any | 否 | Metadata |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## GET `/api/v1/books/{book_id}/notes`

**获取笔记列表**

获取书籍的笔记列表。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| book_id | path | string (uuid) | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## POST `/api/v1/books/{book_id}/notes`

**创建笔记**

创建书籍笔记。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| book_id | path | string (uuid) | 是 |  |

### 请求体

- `Content-Type: application/json`
  - Schema: [BookNoteCreate](./10-schemas.md#BookNoteCreate)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | chapter | any | 否 | Chapter |
    | content | string | 是 | Content |
    | highlight_range | any | 否 | Highlight Range |
    | book_id | string (uuid) | 是 | Book Id |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 201 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## POST `/api/v1/books/{book_id}/parse`

**触发内容解析**

触发书籍内容解析+知识提取（异步任务）。

返回任务 ID，可通过 Celery 结果后端查询任务状态。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| book_id | path | string (uuid) | 是 |  |

### 请求体

_(无请求体)_

### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## PATCH `/api/v1/books/{book_id}/progress`

**更新阅读进度**

更新阅读进度（0.0 ~ 1.0）。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| book_id | path | string (uuid) | 是 |  |

### 请求体

- `Content-Type: application/json`
  - Schema: [BookProgressUpdate](./10-schemas.md#BookProgressUpdate)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | progress | number | 是 | 阅读进度 0.0~1.0 |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |


## POST `/api/v1/books/{book_id}/qa`

**书籍 RAG 问答**

基于书籍内容的 RAG 问答。

检索书中相关知识片段，结合 LLM 生成回答。

### 请求参数

| 名称 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| book_id | path | string (uuid) | 是 |  |

### 请求体

- `Content-Type: application/json`
  - Schema: [BookQARequest](./10-schemas.md#BookQARequest)
  - 字段明细：

    | 字段 | 类型 | 必填 | 说明 |
    |---|---|---|---|
    | question | string | 是 | 问题内容 |
    | top_k | integer | 否 | 检索的知识块数量 |


### 响应

| HTTP | 说明 | Schema |
|---|---|---|
| 200 | Successful Response | any |
| 422 | Validation Error | [HTTPValidationError](./10-schemas.md#HTTPValidationError) |
