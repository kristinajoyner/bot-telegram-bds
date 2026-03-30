"""
BĐS Scoring Bot v3.1 — Telegram Bot
Chấm điểm BĐS tự động + Batch scoring nhiều BĐS cùng lúc
18 hạng mục, 82 tiêu chí, 16 Red Flags
"""

import os
import json
import logging
import asyncio
from dotenv import load_dotenv
from anthropic import Anthropic
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

client = Anthropic(api_key=ANTHROPIC_API_KEY)

# ══════════════════════════════════════════════
# SYSTEM PROMPT — SKILL + SOP nhúng sẵn
# ══════════════════════════════════════════════

SYSTEM_PROMPT_SINGLE = """Bạn là "BĐS Scoring Bot v3.1" — chuyên gia chấm điểm bất động sản tại TP.HCM.

5 QUY TẮC VÀNG:
1. Mỗi điểm số PHẢI có lý do cụ thể
2. Thiếu thông tin = mặc định 4/10 + ghi "⚠️ Chưa xác minh"
3. Red Flag = Từ chối tự động — dính 1 = FAIL
4. Luôn nêu nguồn kiểm tra
5. Thẳng thắn — bảo vệ vốn NĐT là #1

TIẾP NHẬN: Đủ ≥5 mục → phân tích ngay. Thiếu → hỏi 1 lần.

16 RED FLAGS (dính 1 = TỪ CHỐI):
RF1: Chưa có sổ (MPLIS) | RF2: QH giải tỏa (cổng QH) | RF3: Tranh chấp (MPLIS+UBND)
RF4: CĐT lừa đảo (CafeF) | RF5: Giá >20% TT (DKRA) | RF6: Ngập/lún >2cm/năm (Sở NN&MT)
RF7: Đất NN chưa chuyển (QH) | RF8: Hẻm cụt <2m | RF9: Thế chấp không giải chấp (MPLIS)
RF10: Thanh khoản=0 (batdongsan) | RF11: Hành lang an toàn (QH) | RF12: Giấy tờ giả
RF13: Tiền SDĐ chưa đóng (bảng giá 2026) | RF14: GD tiền mặt (Luật ĐĐ 2024)
RF15: Chưa PCCC (TT 05/2024) | RF16: Cao độ < triều cường 2026

18 HẠNG MỤC (82 tiêu chí):
HM1: Pháp lý toàn diện (10%) — Sổ, QH, tranh chấp, GPXD, thế chấp, bảng giá 2026, GD qua NH
HM2: Định giá đa PP (10%) — Comps, giá/m² thông thủy, DCF, Replacement, biên thương lượng
HM3: Tài chính (10%) — Cap Rate (TT~4%,ven~8%), IRR, dòng tiền, vay 9-14%, thuế BĐS thứ 2
HM4: Thanh khoản (9%) — TG bán, nhu cầu thực, khách thuê, vacancy<10%, đại chúng
HM5: Vị trí vi mô (8%) — Metro<1km, walkability, hẻm/MT, an ninh, giao thông
HM6: Vị trí vĩ mô (8%) — Xu hướng quận, VĐ3/Metro2/TT4, TOD, không QH giải tỏa
HM7: Tăng giá (7%) — Xu hướng 3-5 năm, động lực, chênh lệch, dư địa
HM8: Kỹ thuật (7%) — Địa chất, kết cấu, M&E, PCCC, DT thông thủy 70-90%
HM9: Xanh&Smart (6%) — EDGE/LEED, AI, tiết kiệm NL, ESG premium
HM10: CĐT (6%) — Uy tín, tuổi tòa nhà, vật liệu, tiến độ
HM11: Ngập/lún (6%) — Cao độ, lịch sử ngập, thoát nước, sụt lún, ô nhiễm
HM12: Thoát vốn (6%) — ≥2 KB exit, thời điểm, chuyển đổi, KB xấu, timeline
HM13: Phong thủy (5%) — Hướng, hình thế, sát khí đô thị, hóa giải, thanh khoản
HM14: Thuế&phí (5%) — SDĐ 2026, TNCN 2%, trước bạ, sửa chữa, bảo trì
HM15: Nhân khẩu (4%) — Mật độ, thu nhập, dân cư, KCN/ĐH/BV
HM16: Vĩ mô (4%) — Lãi suất, tín dụng, chu kỳ, luật mới
HM17: Stress test (4%) — KB lãi+3%, giá-15%, bán chậm, break-even
HM18: So sánh kênh (3%) — vs tiết kiệm, CK/vàng, chi phí cơ hội

Thang: 9-10 Xuất sắc | 7-8 Tốt | 5-6 TB | 3-4 Yếu | 1-2 Rất yếu
Kết luận: 80-100 MẠNH TAY | 70-79 NÊN MUA | 60-69 CÂN NHẮC | 50-59 THẬN TRỌNG | <50 KHÔNG MUA

Khu vực HCM: Q.1,3,PN,BT nội thành giá cao | TĐ Metro1 cẩn thận lún | Q.7 PMH yield tốt nền bùn | BC,HM giá rẻ TK thấp | Q.8,NB lún>2cm ngập

FORMAT BÁO CÁO:
╔══════════════════════════╗
║ BÁO CÁO CHẤM ĐIỂM BĐS  ║
╚══════════════════════════╝
📋 THÔNG TIN → 🚨 RED FLAGS → 📊 18 HM (điểm+lý do) → 📈 NHÓM → 🏆 TỔNG ĐIỂM → 💪 MẠNH → ⚡ YẾU → 🎯 KHUYẾN NGHỊ → 🔍 XÁC MINH"""


SYSTEM_PROMPT_BATCH = """Bạn là "BĐS Scoring Bot v3.1" — chuyên gia chấm điểm bất động sản tại TP.HCM.

NHIỆM VỤ: Nhận NHIỀU BĐS cùng lúc, chấm điểm TỪNG CÁI theo hệ thống 18 hạng mục (82 tiêu chí) + 16 Red Flags, rồi XẾP HẠNG từ cao đến thấp.

QUY TẮC VÀNG:
1. Mỗi điểm số PHẢI có lý do cụ thể
2. Thiếu thông tin = 4/10 + "⚠️ Chưa xác minh"
3. Red Flag = TỪ CHỐI tự động
4. Luôn nêu nguồn kiểm tra
5. BẢO VỆ VỐN là ưu tiên #1

16 RED FLAGS (dính 1 = TỪ CHỐI):
RF1-12: [chuẩn] + RF13: SDĐ chưa đóng bảng giá 2026 | RF14: GD tiền mặt | RF15: Chưa PCCC | RF16: Cao độ<triều cường

18 HẠNG MỤC với trọng số:
Pháp lý 10% | Định giá 10% | Tài chính 10% | Thanh khoản 9% | Vi mô 8% | Vĩ mô&QH 8% | Tăng giá 7% | Kỹ thuật 7% | Xanh 6% | CĐT 6% | Ngập 6% | Thoát vốn 6% | Phong thủy 5% | Thuế 5% | Nhân khẩu 4% | Vĩ mô 4% | Stress 4% | So sánh 3%

Thang: 80-100 MẠNH TAY | 70-79 NÊN MUA | 60-69 CÂN NHẮC | 50-59 THẬN TRỌNG | <50 KHÔNG MUA

FORMAT BÁO CÁO BATCH — BẮT BUỘC tuân theo format sau:

Đầu tiên, chấm điểm CHI TIẾT từng BĐS (Red Flags + 18 HM + điểm + lý do). Sau đó xuất bảng xếp hạng:

═══════════════════════════════════
🏆 BẢNG XẾP HẠNG BĐS (Cao → Thấp)
═══════════════════════════════════

| Hạng | BĐS | Điểm | Kết luận | Red Flag |
|------|-----|------|----------|----------|
| 1 | [tên] | XX.X | MẠNH TAY ✅ | 0/16 |
| 2 | [tên] | XX.X | NÊN MUA 🟢 | 0/16 |
| ... | ... | ... | ... | ... |

Sau bảng xếp hạng, xuất:

🥇 TOP PICK: [BĐS tốt nhất] — Lý do ngắn gọn tại sao nên ưu tiên
⚠️ NÊN TRÁNH: [BĐS tệ nhất] — Lý do ngắn gọn

📊 SO SÁNH NHANH 5 NHÓM:
| Nhóm | BĐS 1 | BĐS 2 | BĐS 3 | ... |
|------|-------|-------|-------|-----|
| Nền tảng | X/10 | X/10 | ... |
| Giá trị | X/10 | X/10 | ... |
| Vị trí | X/10 | X/10 | ... |
| Sinh lời | X/10 | X/10 | ... |
| Vĩ mô | X/10 | X/10 | ... |

🎯 KHUYẾN NGHỊ CUỐI CÙNG:
[Phân tích so sánh: nên đầu tư BĐS nào, tại sao, với điều kiện gì]

Khu vực HCM: Q.1,3,PN,BT nội thành | TĐ Metro1 | Q.7 PMH | BC,HM vùng ven | Q.8,NB lún ngập
"""


# ══════════════════════════════════════
# Chat history
# ══════════════════════════════════════

user_histories = {}
MAX_HISTORY = 10


def get_history(uid):
    return user_histories.setdefault(uid, [])


def add_msg(uid, role, content):
    h = get_history(uid)
    h.append({"role": role, "content": content})
    if len(h) > MAX_HISTORY:
        user_histories[uid] = h[-MAX_HISTORY:]


def clear_history(uid):
    user_histories[uid] = []


# ══════════════════════════════════════
# Phát hiện batch (nhiều BĐS)
# ══════════════════════════════════════

BATCH_KEYWORDS = [
    "bđs 1", "bds 1", "căn 1", "lô 1", "deal 1",
    "bđs 2", "bds 2", "căn 2", "lô 2", "deal 2",
    "bất động sản 1", "bất động sản 2",
    "so sánh", "xếp hạng", "chấm hết", "đánh giá hết",
    "nhiều bđs", "nhiều bds", "mấy căn", "mấy lô",
    "batch", "danh sách", "list",
    "---", "===", "***",  # separators
]

BATCH_PATTERNS = [
    # Đánh số: "1.", "2.", "1)", "2)"
    lambda t: sum(1 for line in t.split("\n") if line.strip()[:2] in [f"{i}." for i in range(1,10)] or line.strip()[:2] in [f"{i})" for i in range(1,10)]) >= 2,
    # Có >=2 giá tiền riêng biệt
    lambda t: len([w for w in t.split() if "tỷ" in w.lower() or "triệu" in w.lower() or "tr" == w.lower()]) >= 2,
]


def is_batch(text):
    """Phát hiện xem tin nhắn có chứa nhiều BĐS không."""
    lower = text.lower()

    # Check keywords
    keyword_count = sum(1 for kw in BATCH_KEYWORDS if kw in lower)
    if keyword_count >= 2:
        return True

    # Check patterns
    for pattern_fn in BATCH_PATTERNS:
        try:
            if pattern_fn(text):
                return True
        except:
            pass

    # Check nếu text dài và có nhiều dấu phân cách
    separators = text.count("---") + text.count("===") + text.count("***") + text.count("\n\n\n")
    if separators >= 1 and len(text) > 300:
        return True

    return False


# ══════════════════════════════════════
# Gọi Claude API
# ══════════════════════════════════════

def call_claude(uid, user_message, is_batch_mode=False):
    """Gọi Claude API."""
    add_msg(uid, "user", user_message)
    history = get_history(uid)

    system = SYSTEM_PROMPT_BATCH if is_batch_mode else SYSTEM_PROMPT_SINGLE

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            system=system,
            messages=history,
        )
        reply = response.content[0].text
        add_msg(uid, "assistant", reply)
        return reply
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return f"⚠️ Lỗi API: {str(e)}\nVui lòng thử lại."


def call_claude_batch_long(uid, user_message):
    """Gọi Claude cho batch dài — tăng max_tokens."""
    add_msg(uid, "user", user_message)
    history = get_history(uid)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            system=SYSTEM_PROMPT_BATCH,
            messages=history,
        )
        reply = response.content[0].text
        add_msg(uid, "assistant", reply)
        return reply
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return f"⚠️ Lỗi API: {str(e)}"


# ══════════════════════════════════════
# Telegram Handlers
# ══════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    clear_history(uid)
    await update.message.reply_text(
        "🏠 *BĐS Scoring Bot v3\\.1*\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Xin chào\\! Tôi chấm điểm BĐS tự động\\.\n\n"
        "*2 chế độ:*\n"
        "📝 *Đánh giá 1 BĐS* — paste thông tin 1 căn\n"
        "📊 *So sánh nhiều BĐS* — paste nhiều căn, tôi chấm hết rồi xếp hạng\n\n"
        "💡 /vidu — ví dụ mẫu\n"
        "💡 /batch — ví dụ gửi nhiều BĐS\n"
        "🗑 /clear — bắt đầu deal mới",
        parse_mode="MarkdownV2",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Hướng dẫn*\n\n"
        "*Đánh giá 1 BĐS:*\n"
        "Paste thông tin → nhận báo cáo chi tiết\n\n"
        "*So sánh nhiều BĐS:*\n"
        "Paste nhiều căn \\(đánh số 1\\., 2\\., 3\\.\\)\n"
        "→ Nhận báo cáo từng căn \\+ bảng xếp hạng\n\n"
        "*Lệnh:*\n"
        "/start \\- Khởi động\n"
        "/vidu \\- Ví dụ 1 BĐS\n"
        "/batch \\- Ví dụ nhiều BĐS\n"
        "/clear \\- Xóa chat\n"
        "/help \\- Hướng dẫn",
        parse_mode="MarkdownV2",
    )


async def cmd_example(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Ví dụ 1 BĐS* — Copy \\& paste:\n\n"
        "`Sale Minh gửi: Nhà MT Nguyễn Trãi Q.5, "
        "4x18m, 3 tầng, sổ hồng, 22 tỷ, "
        "hẻm xe hơi 8m, xây 2019, hướng ĐN, "
        "cho thuê 35tr/tháng`",
        parse_mode="MarkdownV2",
    )


async def cmd_batch_example(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 *Ví dụ gửi NHIỀU BĐS* — Copy & paste:\n\n"
        "---\n"
        "Chấm điểm và xếp hạng 3 BĐS sau:\n\n"
        "1. Nhà phố MT Lê Văn Sỹ Q.3, 4x20m, 3 tầng, sổ hồng, 28 tỷ, "
        "hẻm xe hơi, xây 2020, hướng ĐN, thuê 45tr/th\n\n"
        "2. Đất nền 120m² Bình Chánh, đường 12m, sổ riêng, 4.2 tỷ, "
        "gần Vành đai 3, đất thổ cư 100%\n\n"
        "3. Căn hộ 2PN 75m² Q.7 Phú Mỹ Hưng, tầng 18, hướng ĐN, "
        "sổ hồng, 5.2 tỷ, CĐT PMH, thuê 20tr/th, PCCC đầy đủ\n"
        "---\n\n"
        "💡 Mẹo: Đánh số 1. 2. 3. hoặc ngăn cách bằng --- để bot nhận diện nhiều BĐS."
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_history(update.effective_user.id)
    await update.message.reply_text(
        "🗑 Đã xóa lịch sử\\.\nSẵn sàng phân tích deal mới\\!",
        parse_mode="MarkdownV2",
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xử lý tin nhắn — tự phát hiện single vs batch."""
    uid = update.effective_user.id
    text = update.message.text

    if not text or len(text.strip()) < 10:
        await update.message.reply_text(
            "Vui lòng gửi thông tin BĐS chi tiết hơn.\n"
            "Tối thiểu: địa chỉ, giá, diện tích, loại hình, pháp lý.\n\n"
            "💡 /vidu — xem ví dụ\n"
            "💡 /batch — xem ví dụ nhiều BĐS"
        )
        return

    # Phát hiện batch
    batch_mode = is_batch(text)

    if batch_mode:
        thinking = await update.message.reply_text(
            "📊 Phát hiện NHIỀU BĐS — đang chấm điểm từng căn và xếp hạng...\n"
            "⏱ Có thể mất 1-3 phút. Vui lòng chờ."
        )
        reply = call_claude_batch_long(uid, text)
    else:
        thinking = await update.message.reply_text(
            "🔍 Đang phân tích BĐS... (30-60 giây)"
        )
        reply = call_claude(uid, text, is_batch_mode=False)

    await thinking.delete()

    # Chia nhỏ nếu dài
    chunks = split_message(reply, 4096)
    for chunk in chunks:
        try:
            await update.message.reply_text(chunk)
        except Exception as e:
            # Fallback nếu lỗi format
            await update.message.reply_text(chunk[:4096])

    # Nếu batch, gửi thêm gợi ý
    if batch_mode:
        await update.message.reply_text(
            "💡 Bạn có thể hỏi thêm:\n"
            "• \"Phân tích sâu hơn BĐS số 1\"\n"
            "• \"So sánh BĐS 1 và 3 chi tiết hơn\"\n"
            "• \"Nếu tôi chỉ có 10 tỷ, nên chọn căn nào?\""
        )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption or ""
    await update.message.reply_text(
        "📸 Nhận được ảnh. Bot xử lý tốt nhất với text.\n\n"
        "Vui lòng mô tả bằng text: địa chỉ, giá, DT, loại hình, pháp lý.\n"
        f"{'Caption: ' + caption if caption else ''}"
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📎 Nhận được file. Vui lòng copy-paste nội dung vào đây."
    )


def split_message(text, max_len=4096):
    """Chia tin nhắn dài."""
    chunks = []
    while len(text) > max_len:
        cut = text.rfind("\n", 0, max_len)
        if cut == -1 or cut < max_len // 2:
            cut = text.rfind(". ", 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


# ══════════════════════════════════════
# Main
# ══════════════════════════════════════

def main():
    if not TELEGRAM_TOKEN:
        print("❌ Thiếu TELEGRAM_TOKEN")
        return
    if not ANTHROPIC_API_KEY:
        print("❌ Thiếu ANTHROPIC_API_KEY")
        return

    print("🏠 BĐS Scoring Bot v3.1")
    print("   Single + Batch scoring")
    print("   18 HM | 82 TC | 16 RF")
    print("   Bot sẵn sàng!")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("vidu", cmd_example))
    app.add_handler(CommandHandler("batch", cmd_batch_example))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
