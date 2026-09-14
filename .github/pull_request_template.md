## 这次改了什么

<!-- 一两句说清楚动机；如果是修 bug，先写"错在哪、影响是什么" -->

## 检查清单

- [ ] `make pytest`（或 `make test`）通过
- [ ] 改了教学材料 → `make handbook-check` 通过，且 PDF / 网页版已同步
- [ ] 改了 `teaching/build_notebooks.py` → 跑过 `make notebooks` 并提交生成的 `notebooks/`
- [ ] 改了实验或模型 → 跑过 `make exp-models` / `make results`，`docs/RESULTS.md` 已刷新
- [ ] 提交信息里没有 AI 协作工具的署名尾注（钩子会自动剔除，CI 会兜底检查）

## 如果引入了新的数字

请说明它属于哪一类（在 `docs/RESULTS.md` 里有对应行才允许写进文档）：

- 语料（corpus）：校园 / BOSSbase npz / BOSSbase csv / 合并 / OOD 真实照片 …
- 协议（protocol）：按源图 holdout / GroupKFold OOF / 8-seed 均值 …
- 生产者：哪个脚本 + 哪个 CSV

做不到可溯源的，请写进 `experiments/PROVENANCE.md` 并说明为什么，不要直接当结论用。

## 已知限制 / 后续

<!-- 可选：写清楚这次**没有**解决什么 -->
