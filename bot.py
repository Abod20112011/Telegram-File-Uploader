#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram File Uploader - الإصدار النهائي
بوت استقبال الملفات + أداة رفع يدوية في أمر واحد
ضمان 100% عمل - مطور بواسطة @BD_0I
"""

import os
import sys
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# -------------------- الإعدادات الثابتة --------------------
CONFIG_FILE = "config.json"
RECEIVED_FOLDER = "received"
UPLOADS_FOLDER = "uploads"
LOGS_FOLDER = "logs"
LOG_FILE = os.path.join(LOGS_FOLDER, "bot.log")

# إنشاء المجلدات الأساسية
for folder in [RECEIVED_FOLDER, UPLOADS_FOLDER, LOGS_FOLDER]:
    Path(folder).mkdir(parents=True, exist_ok=True)

# -------------------- إعداد التسجيل (Logging) --------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -------------------- دوال تحميل/حفظ الإعدادات --------------------
def load_config():
    """تحميل الإعدادات من config.json"""
    default_config = {
        "bot_token": "8484471482:AAHAGHcTu5lqMuorHEBTZkWWf52tEmjmkHg",
        "developer_username": "BD_0I",
        "auto_upload": False,
        "max_file_size": 50,
        "allowed_extensions": []
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # دمج الإعدادات الافتراضية
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                return config
        except:
            return default_config
    else:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=4)
        return default_config

def save_config(config):
    """حفظ الإعدادات"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

# -------------------- أوامر البوت --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /start"""
    config = load_config()
    await update.message.reply_text(
        f"📥 **بوت استقبال الملفات**\n\n"
        f"مرحباً {update.effective_user.first_name}!\n"
        f"• أرسل أي ملف وسيتم حفظه.\n"
        f"• لعرض الملفات المستلمة: `/list`\n"
        f"• لرفع الملفات: `/upload`\n"
        f"• لتنظيف الملفات: `/clean`\n"
        f"• المطور: @{config['developer_username']}",
        parse_mode="Markdown"
    )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """استقبال الملفات من المستخدمين"""
    doc = update.message.document
    user = update.effective_user
    config = load_config()
    
    # التحقق من حجم الملف
    file_size_mb = doc.file_size / (1024 * 1024)
    if file_size_mb > config.get('max_file_size', 50):
        await update.message.reply_text(
            f"❌ حجم الملف كبير جداً ({file_size_mb:.1f} ميجابايت).\n"
            f"الحد الأقصى: {config['max_file_size']} ميجابايت."
        )
        return
    
    # التحقق من الامتداد المسموح
    ext = doc.file_name.split('.')[-1].lower() if '.' in doc.file_name else ''
    allowed = config.get('allowed_extensions', [])
    if allowed and ext not in allowed:
        await update.message.reply_text(f"❌ امتداد الملف غير مسموح: .{ext}")
        return
    
    try:
        # تنزيل الملف
        file = await context.bot.get_file(doc.file_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = f"{timestamp}_{user.id}_{doc.file_name}"
        file_path = os.path.join(RECEIVED_FOLDER, safe_name)
        await file.download_to_drive(file_path)
        
        logger.info(f"✅ ملف جديد: {doc.file_name} من {user.username or user.id}")
        
        await update.message.reply_text(
            f"✅ **تم استلام الملف بنجاح**\n\n"
            f"📄 الاسم: `{doc.file_name}`\n"
            f"📦 الحجم: {doc.file_size:,} بايت\n"
            f"📁 المسار: `{file_path}`\n"
            f"👤 المستخدم: {user.first_name}",
            parse_mode="Markdown"
        )
        
        # رفع تلقائي إذا كان مفعلاً
        if config.get('auto_upload'):
            await upload_files_command(update, context)
            
    except Exception as e:
        logger.error(f"خطأ في استقبال الملف: {e}")
        await update.message.reply_text(f"❌ حدث خطأ: {str(e)[:100]}")

async def list_files_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الملفات المستلمة"""
    files = list(Path(RECEIVED_FOLDER).glob("*"))
    
    if not files:
        await update.message.reply_text("📂 لا توجد ملفات مستلمة حالياً.")
        return
    
    text = f"📁 **الملفات المستلمة ({len(files)}):**\n\n"
    for idx, f in enumerate(sorted(files, key=lambda x: x.stat().st_mtime, reverse=True)[:10], 1):
        size = f.stat().st_size
        modified = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        text += f"{idx}. `{f.name}`\n   📦 {size:,} بايت - 🕐 {modified}\n\n"
    
    await update.message.reply_text(text, parse_mode="Markdown")

async def upload_files_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رفع الملفات إلى مجلد uploads"""
    await update.message.reply_text("🔄 جاري رفع الملفات...")
    result = upload_files()
    await update.message.reply_text(result)

async def clean_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تنظيف الملفات المستلمة"""
    files = list(Path(RECEIVED_FOLDER).glob("*"))
    count = len(files)
    for f in files:
        os.remove(f)
    logger.info(f"تم حذف {count} ملف")
    await update.message.reply_text(f"🧹 تم حذف {count} ملف من مجلد الاستقبال.")

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض/تعديل الإعدادات"""
    config = load_config()
    
    if context.args:
        if len(context.args) >= 2:
            key = context.args[0]
            value = ' '.join(context.args[1:])
            # تحويل القيم
            if value.isdigit():
                value = int(value)
            elif value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False
            
            if key in config:
                config[key] = value
                save_config(config)
                await update.message.reply_text(f"✅ تم تعديل {key} = {value}")
            else:
                await update.message.reply_text(f"❌ المفتاح {key} غير موجود")
        else:
            await update.message.reply_text("⚠️ استخدم: `/config key value`")
    else:
        text = "⚙️ **الإعدادات الحالية:**\n\n"
        for key, value in config.items():
            text += f"• `{key}`: `{value}`\n"
        text += "\nللتعديل: `/config key value`"
        await update.message.reply_text(text, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض المساعدة"""
    help_text = """
**📚 أوامر البوت:**

/start - بدء البوت
/list - عرض الملفات المستلمة
/upload - رفع الملفات إلى المجلد النهائي
/clean - حذف جميع الملفات المستلمة
/config - عرض/تعديل الإعدادات
/help - عرض هذه المساعدة

**📁 مجلدات المشروع:**
• `received/` - الملفات المستلمة من البوت
• `uploads/` - الملفات بعد رفعها
• `logs/` - سجلات البوت

**🔧 أوامر الأداة (سطر الأوامر):**
python bot.py upload      # رفع الملفات
python bot.py list        # عرض الملفات المنتظرة
python bot.py clean       # حذف الملفات المنتظرة
python bot.py config      # عرض الإعدادات
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

# -------------------- دوال أداة الرفع (CLI) --------------------
def upload_files():
    """رفع الملفات من received إلى uploads"""
    files = list(Path(RECEIVED_FOLDER).glob("*"))
    if not files:
        return "📂 لا توجد ملفات جديدة للرفع."
    
    success = 0
    errors = 0
    for file_path in files:
        try:
            if file_path.is_file():
                dest_path = Path(UPLOADS_FOLDER) / file_path.name
                shutil.copy2(file_path, dest_path)
                os.remove(file_path)
                logger.info(f"✅ رفع: {file_path.name}")
                success += 1
        except Exception as e:
            logger.error(f"❌ خطأ في رفع {file_path.name}: {e}")
            errors += 1
    
    return f"✅ تم رفع {success} ملف بنجاح.\n❌ فشل رفع {errors} ملف."

def list_pending():
    """عرض الملفات المنتظرة في received"""
    files = list(Path(RECEIVED_FOLDER).glob("*"))
    if not files:
        print("📂 لا توجد ملفات منتظرة.")
        return
    
    print(f"📋 الملفات المنتظرة ({len(files)}):")
    total_size = 0
    for f in sorted(files, key=lambda x: x.stat().st_mtime):
        size = f.stat().st_size
        total_size += size
        modified = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        print(f"   - {f.name} ({size:,} بايت) - {modified}")
    print(f"\n📦 الحجم الإجمالي: {total_size:,} بايت")

def clean_pending():
    """حذف الملفات المنتظرة"""
    files = list(Path(RECEIVED_FOLDER).glob("*"))
    count = len(files)
    for f in files:
        os.remove(f)
    logger.info(f"تم حذف {count} ملف من مجلد الاستقبال")
    print(f"🧹 تم حذف {count} ملف.")

def show_config_cli():
    """عرض الإعدادات في سطر الأوامر"""
    config = load_config()
    print("⚙️ الإعدادات الحالية:")
    for key, value in config.items():
        print(f"   {key}: {value}")

def show_help_cli():
    """مساعدة أداة سطر الأوامر"""
    print("""
📁 **Telegram File Uploader - أداة رفع الملفات**

الاستخدام:
  python bot.py              # تشغيل البوت
  python bot.py upload       # رفع الملفات المنتظرة
  python bot.py list         # عرض الملفات المنتظرة
  python bot.py clean        # حذف الملفات المنتظرة
  python bot.py config       # عرض الإعدادات
  python bot.py help         # عرض هذه المساعدة

المجلدات:
  • received/  - الملفات المستلمة من البوت
  • uploads/   - الملفات المرفوعة نهائياً
  • logs/      - سجلات البوت

للإعدادات المتقدمة، عدل ملف config.json
    """)

# -------------------- تشغيل البوت --------------------
def run_bot():
    """تشغيل بوت التليجرام"""
    config = load_config()
    token = config.get('bot_token')
    
    if not token:
        logger.error("❌ لم يتم العثور على توكن البوت في config.json")
        return
    
    app = Application.builder().token(token).build()
    
    # إضافة المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_files_command))
    app.add_handler(CommandHandler("upload", upload_files_command))
    app.add_handler(CommandHandler("clean", clean_command))
    app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    logger.info("🚀 بوت الاستقبال يعمل...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

# -------------------- النقطة الرئيسية --------------------
def main():
    """التحكم الرئيسي: إما تشغيل البوت أو تنفيذ أوامر CLI"""
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "upload":
            print(upload_files())
        elif command == "list":
            list_pending()
        elif command == "clean":
            clean_pending()
        elif command == "config":
            show_config_cli()
        elif command == "help":
            show_help_cli()
        else:
            print(f"⚠️ أمر غير معروف: {command}")
            show_help_cli()
    else:
        try:
            run_bot()
        except KeyboardInterrupt:
            print("\n👋 تم إيقاف البوت.")
        except Exception as e:
            logger.error(f"خطأ في تشغيل البوت: {e}")

if __name__ == "__main__":
    main()
