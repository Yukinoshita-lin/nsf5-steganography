# JOSE 投稿论文

面向 [JOSE](https://jose.theoj.org/)（Journal of Open Source Education）的软件论文。

## 文件关系

```
paper.md          ← 投稿的**唯一正文源**（JOSE 规定放仓库根目录）
paper.bib         ← 参考文献（中英两版共用同一份）
paper/
├── paper-en.tex  ← paper.md 的英文排版渲染
├── paper-en.pdf  ── 编译产物，3 页
├── paper-zh.tex  ← 同一内容的中文渲染（便于作者与导师阅读）
└── paper-zh.pdf  ── 编译产物，3 页
```

**改动正文请改 `paper.md`，再同步两个 `.tex`。** 中文版不是投稿材料——JOSE 只收
英文——它存在的意义是让你和导师能直接读。

## 重新编译

```bash
cd paper
xelatex paper-en && bibtex paper-en && xelatex paper-en && xelatex paper-en
# 中文版同理，把 paper-en 换成 paper-zh
```

需要 MiKTeX/TeX Live（含 XeLaTeX）与一份 CJK 字体（中文版用 `fontset=windows`，
即系统自带的微软雅黑/宋体）。`paper.bib` 在上一级目录，故要设置 `BIBINPUTS`：

```bash
BIBINPUTS="$(cd .. && pwd);" xelatex paper-en && BIBINPUTS="$(cd .. && pwd);" bibtex paper-en
```

## 投稿前必须替换的占位符

- [ ] **ORCID**：两个 `.tex` 与 `paper.md` 里现在都是 `0000-0000-0000-0000`。
      JOSE 要求作者提供真实 ORCID，没有的话需要先在 <https://orcid.org> 注册。
- [ ] **单位**：现写作「齐鲁工业大学 / Qilu University of Technology」，取自你
      本地 `thesis/journal_paper.tex` 的署名（该目录不入库）。那里域名写作
      `qlu.edu.com`，中国高校通常为 `.cn`。**这个我没有自行改成 .cn，请核实官方
      英文全称。**
- [ ] **作者姓名拼写**：现用 `Fengjie Lin`（与本地论文署名一致），而 `NOTICE`
      里署的是 `Yushitayuri`。两者需统一。

## 关于引用

`paper.bib` 里的 16 条文献是按通行版本录入的，**投稿前请逐条核对**页码与 DOI
（尤其是卷期号）。我没有逐条访问原文核对，只保证这些是真实存在、且被正确归类的
文献。

## JOSE 评审会检查什么

- 开源许可（Apache-2.0 ✅）
- 可安装、有文档（✅ README + 双语手册 + notebook）
- 有测试与 CI（✅ 24 项测试，三平台）
- 有明确的**教育目标与目标受众**（正文的「目标读者与教学场景」「学习产出」两节）
- 软件**被实际使用过的证据** —— 这是本项目目前最弱的一项，正文里已如实写明
  「尚未在正式课程中采用」，并把「欢迎教师试用」写成明确的合作邀请。不夸大这一点，
  比编一个采用案例更容易过审。
