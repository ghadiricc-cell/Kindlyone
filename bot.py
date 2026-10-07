import asyncio
import json
import os
import urllib.request
import urllib.error

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv


# =========================
# Environment
# =========================

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")

if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN پیدا نشد. فایل .env را بررسی کنید."
    )


# =========================
# Bot
# =========================

dp = Dispatcher()


# =========================
# Backend Request
# =========================

async def api_get(endpoint: str):
    """
    دریافت اطلاعات از Backend بدون نیاز به کتابخانه اضافی.
    """

    url = f"{API_URL}{endpoint}"

    def request():
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                data = response.read().decode("utf-8")
                return json.loads(data)

        except Exception as error:
            print(f"Backend error: {error}")
            return None

    return await asyncio.to_thread(request)


# =========================
# Main Menu
# =========================

def main_menu():
    builder = InlineKeyboardBuilder()

    builder.button(text="❤️ کمک می‌کنم", callback_data="donate")
    builder.button(text="🆘 معرفی یک کیس", callback_data="case")
    builder.button(text="📊 گزارش شفافیت", callback_data="report")
    builder.button(text="📖 درباره ما", callback_data="about")
    builder.button(text="💬 نظرات و پیشنهادات", callback_data="feedback")
    builder.button(text="📞 ارتباط با مدیریت", callback_data="contact")
    builder.button(text="👤 حساب من", callback_data="account")
    builder.button(text="⚙️ تنظیمات", callback_data="settings")

    builder.adjust(2, 2, 2, 2)

    return builder.as_markup()


def back_menu():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="🔙 بازگشت به منوی اصلی",
        callback_data="home"
    )

    return builder.as_markup()


# =========================
# Cases Keyboard
# =========================

def cases_menu(cases):
    builder = InlineKeyboardBuilder()

    for item in cases:
        case_id = item.get("id")
        title = item.get("title", "کیس بدون عنوان")

        builder.button(
            text=f"🆘 {title}",
            callback_data=f"viewcase:{case_id}"
        )

    builder.button(
        text="🔙 بازگشت به منوی اصلی",
        callback_data="home"
    )

    builder.adjust(1)

    return builder.as_markup()


# =========================
# Start
# =========================

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "❤️ به Kindly One خوش آمدی\n\n"
        "اینجا قرار نیست کسی از تو سوءاستفاده کند.\n"
        "اینجایی تا با قلبت تصمیم بگیری که زندگی "
        "برای یک انسان دیگر کمی بهتر شود.\n\n"
        "🌱 کمک کوچک تو می‌تواند برای کسی یک اتفاق بزرگ باشد.\n\n"
        "از منوی زیر انتخاب کن:",
        reply_markup=main_menu()
    )


# =========================
# Donate
# =========================

@dp.callback_query(F.data == "donate")
async def donate(callback):
    await callback.answer()

    data = await api_get("/api/cases")

    if not data or not data.get("success"):
        await callback.message.edit_text(
            "❌ در حال حاضر امکان دریافت لیست کیس‌ها وجود ندارد.\n\n"
            "لطفاً کمی بعد دوباره تلاش کن.",
            reply_markup=back_menu()
        )
        return

    cases = data.get("cases", [])

    active_cases = [
        item for item in cases
        if item.get("status") == "active"
    ]

    if not active_cases:
        await callback.message.edit_text(
            "❤️ کمک می‌کنم\n\n"
            "در حال حاضر کیس فعالی برای کمک وجود ندارد.",
            reply_markup=back_menu()
        )
        return

    await callback.message.edit_text(
        "❤️ <b>کمک می‌کنم</b>\n\n"
        "یکی از کیس‌های فعال را انتخاب کن:\n\n"
        "مبلغ و اطلاعات هر کیس را می‌توانی در مرحله بعد مشاهده کنی.",
        reply_markup=cases_menu(active_cases),
        parse_mode="HTML"
    )


# =========================
# View Case
# =========================

@dp.callback_query(F.data.startswith("viewcase:"))
async def view_case(callback):
    await callback.answer()

    try:
        case_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.message.edit_text(
            "❌ شناسه کیس نامعتبر است.",
            reply_markup=back_menu()
        )
        return

    data = await api_get(f"/api/cases/{case_id}")

    if not data or not data.get("success"):
        await callback.message.edit_text(
            "❌ اطلاعات این کیس در دسترس نیست.",
            reply_markup=back_menu()
        )
        return

    case_data = data.get("case")

    if not case_data:
        await callback.message.edit_text(
            "❌ کیس پیدا نشد.",
            reply_markup=back_menu()
        )
        return

    title = case_data.get("title", "بدون عنوان")
    description = case_data.get("description", "توضیحی ثبت نشده است")
    goal = case_data.get("goal", 0)
    raised = case_data.get("raised", 0)
    currency = case_data.get("currency", "USDT")
    status = case_data.get("status", "unknown")

    try:
        progress = (float(raised) / float(goal)) * 100 if float(goal) > 0 else 0
    except (ValueError, TypeError):
        progress = 0

    progress = min(progress, 100)

    text = (
        f"🆘 <b>{title}</b>\n\n"
        f"{description}\n\n"
        f"🎯 هدف: <b>{goal:g} {currency}</b>\n"
        f"💰 جمع‌آوری شده: <b>{raised:g} {currency}</b>\n"
        f"📈 پیشرفت: <b>{progress:.1f}%</b>\n"
        f"📌 وضعیت: <b>{'فعال' if status == 'active' else status}</b>\n\n"
        "در مرحله بعد، گزینه‌های پرداخت و کیف پول همین کیس "
        "را به این بخش متصل می‌کنیم."
    )

    builder = InlineKeyboardBuilder()

    builder.button(
        text="❤️ کمک به این کیس",
        callback_data=f"paycase:{case_id}"
    )

    builder.button(
        text="🔙 بازگشت به کیس‌ها",
        callback_data="donate"
    )

    builder.button(
        text="🏠 منوی اصلی",
        callback_data="home"
    )

    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


# =========================
# Payment Placeholder
# =========================

@dp.callback_query(F.data.startswith("paycase:"))
async def pay_case(callback):
    await callback.answer()

    try:
        case_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.message.edit_text(
            "❌ شناسه کیس نامعتبر است.",
            reply_markup=back_menu()
        )
        return

    await callback.message.edit_text(
        "❤️ <b>کمک به این کیس</b>\n\n"
        "کیس انتخاب شد.\n\n"
        "در مرحله بعد این قسمت را به سیستم واقعی پرداخت "
        "و کیف پول‌های قابل مدیریت از پنل ادمین متصل می‌کنیم.\n\n"
        f"🆔 شناسه کیس: <code>{case_id}</code>",
        reply_markup=back_menu(),
        parse_mode="HTML"
    )


# =========================
# Introduce Case
# =========================

@dp.callback_query(F.data == "case")
async def case(callback):
    await callback.answer()

    await callback.message.edit_text(
        "🆘 <b>معرفی یک کیس</b>\n\n"
        "اگر شخصی را می‌شناسی که واقعاً در شرایط سختی قرار دارد، "
        "می‌توانی او را برای بررسی به Kindly One معرفی کنی.\n\n"
        "⚠️ برای کاهش سوءاستفاده و کیس‌های جعلی، "
        "معرفی کیس فقط برای افرادی که سابقه کمک دارند فعال خواهد بود.\n\n"
        "این بخش بعداً به سیستم ثبت و بررسی کیس‌ها متصل می‌شود.",
        reply_markup=back_menu(),
        parse_mode="HTML"
    )


# =========================
# Transparency
# =========================

@dp.callback_query(F.data == "report")
async def report(callback):
    await callback.answer()

    data = await api_get("/api/cases")

    if not data or not data.get("success"):
        await callback.message.edit_text(
            "❌ اطلاعات گزارش در دسترس نیست.",
            reply_markup=back_menu()
        )
        return

    cases = data.get("cases", [])

    total_goal = 0
    total_raised = 0
    active_cases = 0

    for item in cases:
        try:
            total_goal += float(item.get("goal", 0))
            total_raised += float(item.get("raised", 0))
        except (ValueError, TypeError):
            pass

        if item.get("status") == "active":
            active_cases += 1

    await callback.message.edit_text(
        "📊 <b>گزارش شفافیت</b>\n\n"
        f"💰 مجموع هدف کیس‌ها: <b>{total_goal:g} USDT</b>\n"
        f"❤️ مجموع کمک ثبت‌شده: <b>{total_raised:g} USDT</b>\n"
        f"🆘 تعداد کیس‌های فعال: <b>{active_cases}</b>\n\n"
        "این اطلاعات مستقیماً از Backend پروژه خوانده می‌شود.",
        reply_markup=back_menu(),
        parse_mode="HTML"
    )


# =========================
# About
# =========================

@dp.callback_query(F.data == "about")
async def about(callback):
    await callback.answer()

    await callback.message.edit_text(
        "📖 <b>درباره Kindly One</b>\n\n"
        "«همه برای یکی، یکی برای همه» ❤️\n\n"
        "Kindly One یک پروژه انسانی مستقل است که "
        "با هدف کمک به افرادی شکل گرفته که در مقطعی از زندگی "
        "به حمایت نیاز دارند.\n\n"
        "ما به دنبال کمک‌های بزرگ نیستیم؛ "
        "گاهی یک کمک کوچک از طرف تعداد زیادی انسان "
        "می‌تواند زندگی یک نفر را تغییر دهد.\n\n"
        "🔐 اطلاعات افراد تا حد امکان محرمانه نگه داشته می‌شود.\n"
        "🤝 این پروژه وابسته به هیچ مؤسسه یا خیریه‌ای نیست.",
        reply_markup=back_menu(),
        parse_mode="HTML"
    )


# =========================
# Feedback
# =========================

@dp.callback_query(F.data == "feedback")
async def feedback(callback):
    await callback.answer()

    await callback.message.edit_text(
        "💬 <b>نظرات و پیشنهادات</b>\n\n"
        "نظر، انتقاد یا پیشنهادی داری؟\n\n"
        "این بخش در مرحله بعد به سیستم ثبت بازخورد متصل می‌شود.",
        reply_markup=back_menu(),
        parse_mode="HTML"
    )


# =========================
# Contact
# =========================

@dp.callback_query(F.data == "contact")
async def contact(callback):
    await callback.answer()

    await callback.message.edit_text(
        "📞 <b>ارتباط با مدیریت</b>\n\n"
        "برای ارتباط با مدیریت Kindly One "
        "می‌توانی از این بخش استفاده کنی.\n\n"
        "این قسمت در مرحله بعد به سیستم ارتباط با مدیریت متصل می‌شود.",
        reply_markup=back_menu(),
        parse_mode="HTML"
    )


# =========================
# Account
# =========================

@dp.callback_query(F.data == "account")
async def account(callback):
    await callback.answer()

    user = callback.from_user

    username = (
        f"@{user.username}"
        if user.username
        else "ندارد"
    )

    await callback.message.edit_text(
        "👤 <b>حساب من</b>\n\n"
        f"نام: {user.first_name or '—'}\n"
        f"نام کاربری: {username}\n"
        f"Telegram ID: <code>{user.id}</code>\n\n"
        "سوابق فعالیت و کمک‌های شما در مرحله بعد "
        "از Database خوانده خواهد شد.",
        reply_markup=back_menu(),
        parse_mode="HTML"
    )


# =========================
# Settings
# =========================

@dp.callback_query(F.data == "settings")
async def settings(callback):
    await callback.answer()

    await callback.message.edit_text(
        "⚙️ <b>تنظیمات</b>\n\n"
        "🌐 زبان\n"
        "🔔 اعلان‌ها\n"
        "🔐 تنظیمات حریم خصوصی\n\n"
        "این قسمت در مراحل بعد تکمیل خواهد شد.",
        reply_markup=back_menu(),
        parse_mode="HTML"
    )


# =========================
# Home
# =========================

@dp.callback_query(F.data == "home")
async def home(callback):
    await callback.answer()

    await callback.message.edit_text(
        "❤️ به Kindly One خوش آمدی\n\n"
        "از منوی زیر انتخاب کن:",
        reply_markup=main_menu()
    )


# =========================
# Run
# =========================

async def main():
    bot = Bot(token=TOKEN)

    print("Kindly One is running...")
    print(f"Backend: {API_URL}")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())