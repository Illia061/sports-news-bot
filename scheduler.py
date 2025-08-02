import asyncio
import schedule
import time
import subprocess
import sys
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
import logging

# Киевское время
KIEV_TZ = ZoneInfo("Europe/Kiev")

def now_kiev() -> datetime:
    """Возвращает текущее время в Киеве"""
    return datetime.now(KIEV_TZ)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

class NewsScheduler:
    def __init__(self):
        # ВАЖНО: Рабочие часы по киевскому времени
        self.working_hours_start = dt_time(6, 0)   # 6:00 по Киеву
        self.working_hours_end = dt_time(1, 0)     # 1:00 по Киеву (следующего дня)
        self.interval_minutes = 20
        self.is_running = False
    
    def is_working_hours(self) -> bool:
        """Проверяет рабочие часы по киевскому времени"""
        current_time_kiev = now_kiev()
        current_hour = current_time_kiev.hour
        
        logger.info(f"🕒 Текущее время (Киев): {current_time_kiev.strftime('%H:%M:%S %d.%m.%Y')}")
        
        # Рабочие часы: с 6:00 до 01:00 (следующего дня)
        # Это означает НЕ рабочие часы: с 01:00 до 06:00
        if 1 <= current_hour < 6:  # с 01:00 до 06:00 - время перерыва
            logger.info(f"⏰ Время перерыва: {current_hour}:xx (01:00-06:00). Бот не работает.")
            return False
        else:
            logger.info(f"✅ Рабочее время: {current_hour}:xx")
            return True
    
    def run_main_bot(self):
        if not self.is_working_hours():
            logger.info("⏰ Сейчас время перерыва (01:00-06:00 по Киеву). Пропускаем запуск.")
            return
        
        if self.is_running:
            logger.warning("⚠️ Бот уже выполняется. Пропускаем запуск.")
            return
        
        self.is_running = True
        current_time_kiev = now_kiev()
        current_time_str = current_time_kiev.strftime('%H:%M:%S %d.%m.%Y')
        
        try:
            logger.info(f"🚀 Запускаем бота в {current_time_str} (Киев)")
            result = subprocess.run(
                [sys.executable, 'main.py'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=600  # 10 минут
            )
            if result.returncode == 0:
                logger.info("✅ Бот завершился успешно")
                if result.stdout:
                    important_lines = [
                        line for line in result.stdout.split('\n') 
                        if any(keyword in line for keyword in ['✅', '❌', '🚫', '📢', '📊'])
                    ]
                    for line in important_lines[-10:]:  # Показываем больше важных строк
                        if line.strip():
                            logger.info(f"   {line.strip()}")
            else:
                logger.error(f"❌ Бот завершился с ошибкой (код {result.returncode})")
                if result.stderr:
                    logger.error(f"Ошибка: {result.stderr}")
                if result.stdout:
                    logger.error(f"
