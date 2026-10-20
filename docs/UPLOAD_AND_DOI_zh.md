# GitHub 上传与 DOI 获取说明

本包已整理为仓库文件夹；没有替您公开上传，也没有生成虚构 DOI。建议仓库名：`water-safe-restoration-three-north`。本包对应“论文配套代码与派生数据”，论文正式发表的 DOI 由期刊/出版社分配，两者可以关联但不能互相冒充。若需要论文预印本 DOI，应另行存档论文并核实投稿政策；本包不包含全文。

## 1. 本包已完成的信息

作者：Aohan Bo；姓 Bo、名 Aohan。单位：Beijing Forestry University, Beijing, China。ORCID：https://orcid.org/0009-0002-0355-0262。按您的选择，代码使用 MIT，作者拥有权利的数据、图件和文档使用 CC BY 4.0；LICENSE 和 LICENSES/ 已完整配置。CITATION.cff 已生成并通过 1.2.0 schema 验证。

拟发布版本是 1.0.0。您只需在建好仓库后，将实际 URL 写入 metadata/publication.json 的 repository_url；发布时填 publication_date；平台签发 DOI 后填 archive_doi。此处空值表示“尚未发生”，不是要自行编造。

更新后运行 `python tools/prepare_metadata.py` 和 `python tools/refresh_checksums.py`。如果 DOI 记录还需要列出其他共同作者，应在正式发布前按真实顺序补入 authors。当前记录只使用您明确提供的一位作者。

## 2. 网页上传到 GitHub（无需 Git 命令）

1. 解压交付的 ZIP。进入其中的 `water-safe-restoration-three-north`，这一层应直接看到 README.md、analysis、data、plots、tools。
2. 登录 GitHub，点击右上角 `+` → `New repository`，填写建议仓库名。可先选 Private 检查，准备公开存档时改为 Public。不要额外勾选自动创建 README、许可证或 .gitignore。
3. 点击 `Create repository`。空仓库页面点击 `uploading an existing file`；已有文件时用 `Add file` → `Upload files`。
4. 将**仓库文件夹内的内容**拖入上传区，保持子目录结构。不要把整个 ZIP 当作仓库代码上传，也不要再套一层同名文件夹。
5. GitHub 网页单文件上限 25 MiB、一次最多 100 个文件。本包文件多于 100 个，建议分两批：第一批在仓库根目录上传整个 `data` 文件夹（内含不到 100 个文件）；第二批在根目录上传其余文件和文件夹（也不到 100 个）。不要把 data/inputs 单独拖到仓库根目录，否则会丢失 data 这一层。每批提交说明可填 `Add research companion files`，点击 `Commit changes`。
6. 检查首页是否渲染 README；data/reference/ 应完整，plots/ 下有 figure4.py 和 figure5.py，根目录没有多余嵌套。核对 .gitignore、.gitattributes 也已上传。若文件选择器隐藏点文件，可通过 `Add file` → `Create new file` 手工按原名添加。

GitHub 的 `Import repository` 主要导入已有 Git 仓库 URL，不是本地 ZIP 导入按钮。大量文件也可使用 GitHub Desktop 的本地仓库发布流程，或下方 Git 命令。

## 3. 命令行上传（替代网页方式）

先在 GitHub 建立空仓库。打开本地解压后的仓库目录，在 PowerShell 中逐行执行：

```powershell
git init -b main
git add .
git commit -m "Prepare reproducible research companion"
git remote add origin https://github.com/YOUR_ACCOUNT/water-safe-restoration-three-north.git
git push -u origin main
```

把 YOUR_ACCOUNT 替换为自己的账号。按 GitHub 的浏览器登录/凭据管理器完成认证，不要把访问令牌写进脚本、CSV 或 README。若提示作者身份未配置，按自己的实际姓名/邮箱设置本仓库 Git 身份后再提交。本包没有预设 Git 作者或远程地址。

## 4. 推荐流程：GitHub + Zenodo 正式 DOI

1. 确认作者、许可、仓库内容、版本号，完成 CITATION.cff 后再发布。当前 VERSION 与 CITATION.cff 均为 `1.0.0`，对应 tag `v1.0.0`。
2. 使用正式站点 https://zenodo.org 登录，连接 GitHub 账号。在 Zenodo 个人菜单 `GitHub` 中同步仓库并打开该仓库的存档开关。
3. 回 GitHub 仓库 `Releases` → `Create a new release`，新建 tag（如与元数据一致的 `v1.0.0`），标题写 `Research companion v1.0.0`，说明可参考 docs/RELEASE_NOTES.md。不要只创建 tag 或只保存草稿；发布 release 才会触发集成。
4. 等待 Zenodo 处理。打开生成的记录，核对资源类型、作者顺序、标题、版本、许可、文件列表和 DOI，并检查归档状态。本包采用两种许可；在 Zenodo 中检查并同时列出 MIT 和 CC BY 4.0，说明前者用于代码、后者用于数据/图件/文档。Zenodo 官方支持 mixed license uploads；不要只保留平台默认的一个许可。
5. 将平台实际签发的 DOI 更新到 metadata/publication.json 的 archive_doi、CITATION.cff、README 及论文 Data and code availability。引用复现某一版本时使用该版本 DOI；总概念 DOI 可用于指向跨版本成果。后续更改代码/数据应建新版本，不覆盖已经引用的版本。

GitHub 本身不签发 DOI。普通 push 不等于 release，建了仓库也不等于已有 DOI。DOI 是平台分配的持久标识，不能自己指定一个 `10.xxxx/...` 字符串使其生效。

## 5. 手动 Zenodo 上传（适合先预留 DOI，并准确设置混合许可）

此方式同样可以配合 GitHub 仓库使用，而且本包已经准备好可复制到表单的 `metadata/ZENODO_FORM_zh.txt`。GitHub 自动集成流程不能预留 DOI。可改走 Zenodo 手动上传：新建 upload，在 DOI 问题选“没有已有 DOI”，点击 `Get a DOI now!` 预留号码，将其写进元数据和论文后上传最终包并发布。预留号码不等于已经公开、可解析的正式记录；必须完成发布。

手动存档与 GitHub 自动存档选择一种作为该版本的主记录，避免同一内容重复登记。已有论文 DOI 不能填成这份数据/代码上传的已有 DOI；应在关联标识中使用文章 DOI，关系设为 `isSupplementTo`。若同一研究包本身已有 DOI，则应沿用该记录的版本机制。

## 6. 可填入论文的文字（完成发布后使用）

“The code and derived data supporting this study are available at [actual GitHub URL] and archived in Zenodo at [actual version DOI]. The archive includes the aggregated analytical inputs, R02–R09 scripts, revised Pareto and management tables, and Figure 4–5 plotting scripts. Original remote-sensing preprocessing and reference-domain sample generation are outside the supplied archive.”

方括号内容必须换成真实地址；发布前不能声称 already available。本包的复现边界详见 SCOPE_AND_PROVENANCE.md。

## 核实过的官方说明（2026-10-18）

- GitHub 建仓库：https://docs.github.com/en/repositories/creating-and-managing-repositories/creating-a-new-repository
- GitHub 网页文件/数量限制：https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository
- 引用文件：https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-citation-files
- Zenodo 开启集成：https://help.zenodo.org/docs/github/enable-repository/
- Release 存档：https://help.zenodo.org/docs/github/archive-software/github-upload/
- 预留 DOI：https://help.zenodo.org/docs/deposit/describe-records/reserve-doi/
- GitHub 集成不支持预留：https://support.zenodo.org/help/en-gb/3-github-integration/73-can-i-pre-reserved-a-doi-before-a-github-release
- 许可选择：https://help.zenodo.org/docs/deposit/describe-records/licenses/

Zenodo 同时看到 .zenodo.json 和 CITATION.cff 时优先采用前者。本包只生成 CITATION.cff，减少两套元数据不一致的问题；复杂关联和混合许可请在 Zenodo 记录中核对。
