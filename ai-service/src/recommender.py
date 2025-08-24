from flask import Flask, request, jsonify
from flask_cors import CORS
from collections import defaultdict

app = Flask(__name__)
CORS(app)

# 지원 카테고리
CATEGORIES = ['스포츠', '음식', '의류', '학습', '전자기기']

# 간단한 온라인 학습 모델: 사용자별 카테고리 선호도 카운트
user_category_counts = defaultdict(lambda: defaultdict(int))
user_product_counts = defaultdict(lambda: defaultdict(int))


@app.route('/train', methods=['POST'])
def train():
    """구매 이벤트를 받아 사용자 선호도를 온라인 업데이트한다."""
    data = request.get_json() or {}
    user_id = data.get('userId')
    category = data.get('category')
    product_id = data.get('productId')

    if not user_id or not category:
        return jsonify({'message': 'userId and category are required'}), 400

    if category not in CATEGORIES:
        # 알 수 없는 카테고리는 무시하되 200 반환
        return jsonify({'message': 'ignored'}), 200

    user_category_counts[user_id][category] += 1
    if product_id:
        user_product_counts[user_id][product_id] += 1
    return jsonify({'message': 'ok', 'counts': user_category_counts[user_id]}), 200


@app.route('/recommend', methods=['POST'])
def recommend():
    """사용자의 선호도와 카탈로그를 바탕으로 상위 K개 상품을 반환한다.

    입력 형식:
      {
        "userId": "...",
        "catalog": [{"_id":"..", "name":"..", "category":".."}, ...],
        "purchasedIds": ["...", ...],
        "k": 5
      }
    출력: [상품명, ...] 길이<=k
    """
    data = request.get_json() or {}
    user_id = data.get('userId')
    catalog = data.get('catalog') or []
    purchased_ids = set(data.get('purchasedIds') or [])
    k = int(data.get('k') or 5)

    # 카테고리 목록 추출
    categories = list({p.get('category') for p in catalog if p.get('category')}) or CATEGORIES

    # 사용자 선호도
    cat_counts = user_category_counts.get(user_id, {}) if user_id else {}
    prod_counts = user_product_counts.get(user_id, {}) if user_id else {}

    total_cat = sum(cat_counts.values()) or 0
    num_cat = max(len(categories), 1)

    def cat_score(category: str) -> float:
        # 라플라스 스무딩
        return (cat_counts.get(category, 0) + 1) / (total_cat + num_cat)

    def item_score(item) -> float:
        # 가중치: 카테고리 선호 0.8 + (해당 상품 반복 구매 성향) 0.2
        s_cat = cat_score(item.get('category'))
        s_item = prod_counts.get(item.get('_id'), 0)
        # 정규화: 1 + count의 로그 스케일
        s_item_norm = 1.0 + (0 if s_item == 0 else min(1.0, 0.3 + 0.2 * s_item))
        return 0.8 * s_cat * s_item_norm

    # 후보: 아직 구매하지 않은 상품만
    candidates = [p for p in catalog if p.get('_id') not in purchased_ids]
    # 점수 기준 정렬 후 상위 K개
    ranked = sorted(candidates, key=item_score, reverse=True)[:k]
    return jsonify([p.get('name') for p in ranked])


if __name__ == '__main__':
    app.run(port=5001)
