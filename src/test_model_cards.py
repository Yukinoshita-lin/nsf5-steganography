"""部署模型卡的契约自测 (2026-09-15, 模型治理)。

守的是一件此前完全没有护栏的事: **随仓库分发的两个 .joblib 是裸二进制**。
payload 里虽然写了 provenance, 但读到它要反序列化一个 2.8 MB 的 pickle;
没有模型卡的话, "这个模型是什么、能不能用在我的场景里" 只能靠翻 README 的
某一段散文, 而且 README 一改就没人知道模型是不是也跟着改了。

因此 models/<模型名>.card.json 入库, 并由本文件把它钉在三处事实上:

1. **二进制指纹** (sha256 / bytes) —— 模型一改, 卡不重新生成就会红;
2. **payload 字段** (features 顺序、阈值、held-out AUC、超参、provenance)
   —— 卡里写的必须就是二进制里写的, 不能各说各话;
3. **指标 CSV** (`experiments/data/*.csv`, 产物不入库) —— 在本地有数据时
   交叉核对卡片里的 AUC / 误报率; CI 上这些文件不存在, 明确跳过而不是假装通过。

同时要求每张卡都带**适用边界与已知局限** (intended_use / not_intended_use /
known_limitations)。只报喜不报忧的模型卡比没有模型卡更糟。
"""
import json
import os
import sys

PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(PROJ, "src"), os.path.join(PROJ, "experiments")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import model_card as MC  # noqa: E402

MODEL_FILES = sorted(MC.SPECS)


def _card(model_file):
    card, path = MC._load_card(model_file)
    assert card is not None, f"缺少模型卡 {path}; 跑 python experiments/model_card.py"
    return card


def test_every_shipped_model_has_a_card():
    """models/ 下随仓库分发的每个 .joblib 都必须有卡与之一一对应。"""
    for model_file in MODEL_FILES:
        card = _card(model_file)
        assert card["file"] == model_file
        assert card["schema"] == MC.SCHEMA
        assert os.path.exists(os.path.join(MC.MODEL_DIR, model_file))


def test_card_matches_model_binary():
    """sha256 是硬绑定: 二进制变了卡就必须重生成。"""
    for model_file in MODEL_FILES:
        card = _card(model_file)
        path = os.path.join(MC.MODEL_DIR, model_file)
        assert card["sha256"] == MC.sha256_of(path), \
            f"{model_file} 的 sha256 与模型卡不符 -> 跑 python experiments/model_card.py"
        assert card["bytes"] == os.path.getsize(path)


def test_card_payload_matches_binary():
    """卡里声明的特征顺序 / 阈值 / 超参必须逐位等于二进制里的 payload。

    特征顺序单列: LightGBM 的特征捆绑对列序敏感, 换序会让 AUC 漂移, 所以
    "集合相同" 不够, 必须是同一个列表。
    """
    for model_file in MODEL_FILES:
        card = _card(model_file)
        pkg = MC.load_payload(os.path.join(MC.MODEL_DIR, model_file))
        pb = card["payload"]
        assert pb["features"] == list(pkg["features"])
        assert pb["n_features"] == len(pkg["features"])
        assert pb["threshold"] == float(pkg["threshold"])
        assert pb["threshold_low_fp"] == float(pkg["threshold_low_fp"])
        assert pb["held_out_auc"] == float(pkg["held_out_auc"])
        assert pb["params"] == dict(pkg["params"])
        assert pb["name"] == pkg["name"]


def test_card_training_provenance_matches_binary():
    """溯源字段 (语料 / 协议 / 划分 / 环境 / git rev) 也必须在卡里如实出现。"""
    for model_file in MODEL_FILES:
        card = _card(model_file)
        pkg = MC.load_payload(os.path.join(MC.MODEL_DIR, model_file))
        prov = pkg["provenance"]
        tr = card["training"]
        assert tr["producer"] == prov["producer"]
        assert tr["dataset"] == prov["dataset"]
        assert tr["split"] == prov["split"]
        assert tr["split"]["by"] == "photo_id", "划分必须按源图 (评测纪律第 1 条)"
        assert tr["splits_evaluated"] == MC._norm_splits(prov["splits_evaluated"])
        assert tr["mean_auc_8split"] == prov["mean_auc_8split"]
        assert tr["git_rev"] and tr["trained_at"]


def test_feature_groups_add_up():
    """特征分组要能把维数加回 n_features —— 否则卡在描述另一个模型。"""
    for model_file in MODEL_FILES:
        card = _card(model_file)
        total = sum(g["n"] for g in card["feature_groups"])
        assert total == card["payload"]["n_features"], \
            f"{model_file}: 分组合计 {total} != {card['payload']['n_features']} 维"


def test_card_states_boundaries_not_only_hype():
    """适用边界、不适用场景、已知局限三块都不能是空的套话。"""
    for model_file in MODEL_FILES:
        card = _card(model_file)
        for key in ("intended_use", "not_intended_use", "known_limitations"):
            items = card.get(key) or []
            assert len(items) >= 2, f"{model_file}: {key} 至少写两条"
            assert all(isinstance(x, str) and len(x) > 12 for x in items)
        # 跨语料参考必须带上"不许和校园语料并列"的说明, 否则读者会把
        # 0.8939 与 0.8062 当成同一个口径。
        cross = card["metrics"]["cross_corpus_reference"]
        assert cross["dataset"].startswith("BOSSbase")
        assert cross["auc"] < card["payload"]["held_out_auc"]


def test_card_check_is_clean():
    """`model_card.py --check` 与 pytest 共用同一套逻辑, 这里跑的就是 CI 里那一步。

    这条在本地与 CI 都会执行: sha256 / payload / 结构三块只依赖入库文件;
    指标 CSVs 存在时 (本地) 会额外核对卡片里的 AUC 与误报率, 不在库时 (CI)
    明确打印跳过 —— 所以断言写的是"没有不一致", 不是"全部核对过"。
    """
    problems = MC.check_cards()
    assert problems == [], "\n".join(problems)


def test_cards_are_valid_json_with_expected_keys():
    for model_file in MODEL_FILES:
        path = MC.card_path(model_file)
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        for key in ("schema", "file", "sha256", "bytes", "display_name", "role",
                    "payload", "training", "metrics", "feature_groups",
                    "intended_use", "not_intended_use", "known_limitations"):
            assert key in raw, f"{os.path.basename(path)} 缺少字段 {key}"
        # 卡片必须是 UTF-8 无 BOM 且以换行结尾 (diff 干净)
        with open(path, "rb") as fh:
            blob = fh.read()
        assert not blob.startswith(b"\xef\xbb\xbf")
        assert blob.endswith(b"\n")
