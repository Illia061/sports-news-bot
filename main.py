
import os
from parser import get_latest_news
from ai_processor import summarize_news, simple_summarize

def main():
    print("Бот стартовал")
    
    # Получаем новости
    news_list = get_latest_news()
    
    if not news_list:
        print("Новости не найдены")
        return
    
    print(f"Найдено новостей: {len(news_list)}")
    
    # Проверяем наличие OpenAI API ключа
    has_openai_key = bool(os.getenv("OPENAI_API_KEY"))
    
    if not has_openai_key:
        print("⚠️  OpenAI API ключ не найден. Используем простые резюме.")
    
    results = []
    
    for i, news in enumerate(news_list, 1):
        print(f"Обрабатываем новость {i}/{len(news_list)}: {news['title'][:50]}...")
        
        try:
            if has_openai_key:
                # Используем AI для создания резюме
                summary = summarize_news(news["title"], news["link"])
            else:
                # Используем простое резюме без AI
                summary = simple_summarize(news["title"], news["link"])
            
            result = {
                "title": news["title"],
                "link": news["link"], 
                "summary": summary
            }
            results.append(result)
            
        except Exception as e:
            print(f"Ошибка при обработке новости: {e}")
            # Добавляем новость без резюме
            results.append({
                "title": news["title"],
                "link": news["link"],
                "summary": f"🔸 {news['title']}"
            })
    
    # Выводим результаты
    print("\n" + "="*60)
    print("📰 ФУТБОЛЬНЫЕ НОВОСТИ")
    print("="*60)
    
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['title']}")
        print(f"📝 {result['summary']}")
        print(f"🔗 {result['link']}")
        print("-" * 60)
    
    print(f"\n✅ Обработано {len(results)} новостей")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️  Программа остановлена пользователем")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
