import asyncio
import schedule
import time
import subprocess
import sys
from datetime import datetime, time as dt_time, timezone
from zoneinfo import ZoneInfo
import logging

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
        self.working_hours_start = time(3, 0)  # 6:00 EEST = 3:00 UTC
        self.working_hours_end = time(22, 0)   # 1:00 EEST = 22:00 UTC
        self.interval_minutes = 20
        self.is_running = False
    
    def is_working_hours(self) -> bool:
        current_time = datetime.now(ZoneInfo("Europe/Kiev"))
        logger.info(f"🕒 Текущее время: {current_time} (UTC: {current_time.astimezone(timezone.utc)})")
        if self.working_hours_end <= current_time.time() < self.working_hours_start:
            return False
        return True
    
    def run_main_bot(self):
        if not self.is_working_hours():
            logger.info("⏰ Сейчас время перерыва (1:00-6:00). Пропускаем запуск.")
            return
        
        if self.is_running:
            logger.warning("⚠️ Бот уже выполняется. Пропускаем запуск.")
            return
        
        self.is_running = True
        current_time = datetime.now().strftime('%H:%M:%S %d.%m.%Y')
        
        try:
            logger.info(f"🚀 Запускаем бота в {current_time}")
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
                        if any(keyword in line for keyword in ['✅', '❌', '🚫', '📢'])
                    ]
                    for line in important_lines[-5:]:
                        if line.strip():
                            logger.info(f"   {line.strip()}")
            else:
                logger.error(f"❌ Бот завершился с ошибкой (код {result.returncode})")
                if result.stderr:
                    logger.error(f"Ошибка: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.error("❌ Превышен таймаут выполнения (10 минут)")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска бота: {e}")
        finally:
            self.is_running = False
            logger.info("🔄 Флаг is_running сброшен")
    
    def start_scheduler(self):
        logger.info("🔄 Запуск планировщика новостного бота")
        logger.info(f"⏰ Рабочие часы: {self.working_hours_start.strftime('%H:%M')} - {self.working_hours_end.strftime('%H:%M')} (UTC)")
        logger.info(f"🕐 Интервал: каждые {self.interval_minutes} минут")
        
        schedule.every(self.interval_minutes).minutes.do(self.run_main_bot)
        
        if self.is_working_hours():
            logger.info("🎯 Запускаем первую проверку сразу...")
            self.run_main_bot()
        else:
            logger.info("⏰ Сейчас время перерыва. Ждем начала рабочего дня...")
        
        try:
            while True:
                schedule.run_pending()
                logger.info("🔍 Цикл планировщика выполняется")
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("⏹️ Планировщик остановлен пользователем")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка планировщика: {e}")
            raise

def main():
    logger.info("🎯 АВТОМАТИЧЕСКИЙ ПЛАНИРОВЩИК НОВОСТНОГО БОТА")
    try:
        scheduler = NewsScheduler()
        scheduler.start_scheduler()
    except ImportError:
        logger.warning("⚠️ Модуль schedule недоступен, используем упрощенный планировщик")
        simple_scheduler = SimpleScheduler()
        asyncio.run(simple_scheduler.run_continuous())
    except Exception as e:
        logger.error(f"❌ Ошибка обычного планировщика: {e}")
        logger.info("🔄 Переключаемся на упрощенный планировщик")
        simple_scheduler = SimpleScheduler()
        asyncio.run(simple_scheduler.run_continuous())

if __name__ == "__main__":
    main()
