#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import schedule
import time
import subprocess
import sys
from datetime import datetime, time as dt_time
import logging
import os

# Настройка логирования
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
    """Планировщик для автоматического запуска бота"""
    
    def __init__(self):
        self.working_hours_start = dt_time(6, 0)   # 6:00 утра
        self.working_hours_end = dt_time(1, 0)     # 1:00 ночи (следующего дня)
        self.interval_minutes = 20
        self.is_running = False
    
    def is_working_hours(self) -> bool:
        """Проверяет, рабочее ли время"""
        current_time = datetime.now().time()
        
        # Особый случай: с 1:00 до 6:00 - перерыв
        if self.working_hours_end <= current_time < self.working_hours_start:
            return False
        
        return True
    
    def run_main_bot(self):
        """Запускает основной бот"""
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
            
            # Запускаем main.py в подпроцессе
            result = subprocess.run(
                [sys.executable, 'main.py'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=300  # 5 минут таймаут
            )
            
            if result.returncode == 0:
                logger.info("✅ Бот завершился успешно")
                if result.stdout:
                    # Логируем только важные строки
                    important_lines = [
                        line for line in result.stdout.split('\n') 
                        if any(keyword in line for keyword in [
                            '✅', '❌', '🚫', '📢', 'УСПЕШНО', 'ОШИБКА', 'ДУБЛИКАТ'
                        ])
                    ]
                    for line in important_lines[-5:]:  # Последние 5 важных строк
                        if line.strip():
                            logger.info(f"   {line.strip()}")
            else:
                logger.error(f"❌ Бот завершился с ошибкой (код {result.returncode})")
                if result.stderr:
                    logger.error(f"Ошибка: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Превышен таймаут выполнения (5 минут)")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска бота: {e}")
        finally:
            self.is_running = False
    
    def start_scheduler(self):
        """Запускает планировщик"""
        logger.info("🔄 Запуск планировщика новостного бота")
        logger.info(f"⏰ Рабочие часы: {self.working_hours_start.strftime('%H:%M')} - {self.working_hours_end.strftime('%H:%M')}")
        logger.info(f"🕐 Интервал: каждые {self.interval_minutes} минут")
        logger.info("=" * 60)
        
        # Настраиваем расписание - каждые 20 минут
        schedule.every(self.interval_minutes).minutes.do(self.run_main_bot)
        
        # Запускаем первый раз сразу (если рабочее время)
        if self.is_working_hours():
            logger.info("🎯 Запускаем первую проверку сразу...")
            self.run_main_bot()
        else:
            logger.info("⏰ Сейчас время перерыва. Ждем начала рабочего дня...")
        
        # Основной цикл планировщика
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Проверяем каждую минуту
                
                # Логируем статус каждый час
                current_time = datetime.now()
                if current_time.minute == 0:  # Каждый час
                    if self.is_working_hours():
                        logger.info(f"📊 Планировщик активен. Следующий запуск через {schedule.idle_seconds():.0f} сек.")
                    else:
                        next_work_start = datetime.combine(
                            current_time.date() if current_time.time() >= self.working_hours_start 
                            else current_time.date(),
                            self.working_hours_start
                        )
                        if current_time.time() >= self.working_hours_start:
                            next_work_start = next_work_start.replace(day=next_work_start.day + 1)
                        
                        hours_until_work = (next_work_start - current_time).total_seconds() / 3600
                        logger.info(f"😴 Время перерыва. До начала работы: {hours_until_work:.1f} часов")
                
        except KeyboardInterrupt:
            logger.info("⏹️ Планировщик остановлен пользователем")
        except Exception as e:
            logger.error(f"💥 Критическая ошибка планировщика: {e}")
            raise
    
    def test_schedule(self):
        """Тестирует планировщик"""
        logger.info("🧪 ТЕСТИРОВАНИЕ ПЛАНИРОВЩИКА")
        logger.info("=" * 40)
        
        current_time = datetime.now()
        logger.info(f"🕐 Текущее время: {current_time.strftime('%H:%M:%S %d.%m.%Y')}")
        logger.info(f"⏰ Рабочие часы: {self.working_hours_start.strftime('%H:%M')} - {self.working_hours_end.strftime('%H:%M')}")
        logger.info(f"✅ Сейчас рабочее время: {'Да' if self.is_working_hours() else 'Нет'}")
        
        # Тестируем несколько времен
        test_times = [
            dt_time(5, 30),   # До работы
            dt_time(6, 0),    # Начало работы
            dt_time(12, 0),   # Середина дня
            dt_time(23, 0),   # Вечер
            dt_time(1, 0),    # Конец работы
            dt_time(3, 0),    # Ночь
        ]
        
        logger.info("\n🔍 Тест различных времен:")
        for test_time in test_times:
            # Временно меняем текущее время для теста
            original_time = datetime.now().time
            datetime.now = lambda: datetime.combine(datetime.today(), test_time)
            
            is_working = self.is_working_hours()
            status = "🟢 Работаем" if is_working else "🔴 Перерыв"
            logger.info(f"   {test_time.strftime('%H:%M')} - {status}")
            
            # Восстанавливаем оригинальное время
            datetime.now = lambda: datetime.combine(datetime.today(), original_time())


class SimpleScheduler:
    """Упрощенный планировщик для Railway (если schedule не работает)"""
    
    def __init__(self):
        self.working_hours_start = 6   # 6:00
        self.working_hours_end = 1     # 1:00 (следующего дня)
        self.interval_minutes = 20
    
    def is_working_time(self) -> bool:
        """Проверяет рабочее время"""
        current_hour = datetime.now().hour
        
        # С 1:00 до 6:00 - перерыв
        if 1 <= current_hour < 6:
            return False
        return True
    
    async def run_continuous(self):
        """Непрерывный цикл с проверками"""
        logger.info("🔄 Запуск упрощенного планировщика")
        logger.info(f"⏰ Рабочие часы: 06:00 - 01:00")
        logger.info(f"🕐 Интервал: каждые {self.interval_minutes} минут")
        
        while True:
            try:
                current_time = datetime.now()
                
                if self.is_working_time():
                    logger.info(f"🚀 Запуск бота: {current_time.strftime('%H:%M:%S')}")
                    
                    # Запускаем main.py
                    process = await asyncio.create_subprocess_exec(
                        sys.executable, 'main.py',
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    try:
                        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
                        
                        if process.returncode == 0:
                            logger.info("✅ Бот завершился успешно")
                        else:
                            logger.error(f"❌ Бот завершился с ошибкой: {stderr.decode()}")
                            
                    except asyncio.TimeoutError:
                        logger.error("❌ Таймаут выполнения бота")
                        process.kill()
                    
                    # Ждем 20 минут
                    logger.info(f"⏳ Ждем {self.interval_minutes} минут до следующего запуска...")
                    await asyncio.sleep(self.interval_minutes * 60)
                    
                else:
                    # Время перерыва - ждем до 6:00
                    next_run_hour = 6
                    current_hour = current_time.hour
                    
                    if current_hour >= 6:  # Если уже после 6, то следующий запуск завтра
                        hours_to_wait = 24 - current_hour + 6
                    else:  # Если до 6, ждем до 6
                        hours_to_wait = 6 - current_hour
                    
                    minutes_to_wait = hours_to_wait * 60
                    logger.info(f"😴 Время перерыва. Ждем {hours_to_wait} часов до 06:00...")
                    await asyncio.sleep(minutes_to_wait * 60)
                
            except Exception as e:
                logger.error(f"❌ Ошибка в планировщике: {e}")
                await asyncio.sleep(300)  # Ждем 5 минут при ошибке


def main():
    """Главная функция планировщика"""
    logger.info("🎯 АВТОМАТИЧЕСКИЙ ПЛАНИРОВЩИК НОВОСТНОГО БОТА")
    logger.info("=" * 60)
    
    # Проверяем аргументы командной строки
    if len(sys.argv) > 1:
        if sys.argv[1] == 'test':
            scheduler = NewsScheduler()
            scheduler.test_schedule()
            return
        elif sys.argv[1] == 'simple':
            logger.info("🔧 Используем упрощенный планировщик")
            simple_scheduler = SimpleScheduler()
            asyncio.run(simple_scheduler.run_continuous())
            return
    
    # Пытаемся использовать обычный планировщик
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