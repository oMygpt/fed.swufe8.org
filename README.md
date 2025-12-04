# 应用经济学模型建设 · 收集语料

本仓库旨在搭建基于 Streamlit 的语料收集与管理平台，服务于应用经济学模型的构建与验证。项目包含认证、语料采集与解析、存储管理、基础 UI 展示等模块，并配套单元测试与容器化配置。

## 项目结构
```
.
├── app.py                      # Streamlit 应用入口
├── requirements.txt            # Python 依赖
├── Dockerfile                  # 容器构建文件
├── PRD.md                      # 需求与实施计划
├── config/
│   └── users.yaml              # 用户与权限配置
├── modules/
│   ├── __init__.py
│   ├── auth.py                 # 认证与权限
│   ├── parsing.py              # 解析与清洗
│   ├── storage.py              # 存储与版本化
│   ├── ui.py                   # Streamlit 页面/组件
│   └── utils.py                # 通用工具
└── tests/
    ├── test_auth.py
    ├── test_parsing.py
    └── test_storage.py
```

## 快速开始
- 安装依赖：`pip install -r requirements.txt`
- 启动应用：`streamlit run app.py`
- 配置账号：编辑 `config/users.yaml`

## 运行与部署
- 本地运行：`streamlit run app.py`
- 容器化：
  - 构建：`docker build -t ae-corpus:latest .`
  - 运行：`docker run -p 8501:8501 ae-corpus:latest`

## 测试
- 运行所有用例：`python -m unittest discover -s tests -p "test_*.py"`
- 典型用例：
  - 认证：`tests/test_auth.py`
  - 解析：`tests/test_parsing.py`
  - 存储：`tests/test_storage.py`

## 进度概览
- 认证模块（`modules/auth.py`）：初版实现，含基础单元测试
- 解析模块（`modules/parsing.py`）：初版实现，支持 Excel/CSV 基础解析
- 存储模块（`modules/storage.py`）：初版实现，支持本地存储
- UI（`modules/ui.py`）：基础页面与交互待完善
- 配置（`config/users.yaml`）：基础结构已建立，需完善校验逻辑

## TODO
- [ ] 完成用户认证与角色管理的完善与异常处理
- [ ] 语料采集表单的数据校验与错误提示
- [ ] 数据存储层支持云端（如 S3）与版本化策略
- [ ] 解析与清洗管道覆盖更多格式（Excel/CSV/JSON）
- [ ] Streamlit 页面布局与导航优化
- [ ] `config/users.yaml` 加载与校验、热更新机制
- [ ] 单元测试覆盖率提升至 80%+
- [ ] Docker 镜像构建与基本部署脚本

## 参考与文档
- 需求文档：`PRD.md`
- 计划草案：`.trae/documents/依据 PRD 实现语料库收集管理平台（Streamlit）实施计划.md`

