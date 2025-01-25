import io
import logging.config
import os
import re
import zipfile
from environs import Env

import pandas as pd
import requests

logger = logging.getLogger(__file__)


def get_product_list(last_id, client_id, seller_token):
    """Получить список товаров магазина озон

    Args:
        last_id(str): Идентификатор последнего полученного товара
        client_id(str): Идентификатор клиента
        seller_token(str): Токен продавца
        
    Returns:
        dict: Возвращает словарь содержащий список товаров
        
    Raises:
        requests.exceptions.HTTPError: Если HTTP-запрос завершился неудачно
        ValueError: Если обязательные параметры не переданы или имеют неверный тип
        
    Examples:
        >>> client_id = "your_client_id"
        >>> seller_token = "your_seller_token"
        >>> last_id = "0"
        >>> get_product_list(last_id, client_id, seller_token)
        {"items": [...], "last_id": "123456", ...}
        
    """
    url = "https://api-seller.ozon.ru/v2/product/list"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {
        "filter": {
            "visibility": "ALL",
        },
        "last_id": last_id,
        "limit": 1000,
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def get_offer_ids(client_id, seller_token):
    """Получить артикулы товаров магазина озон
    
    Args:
        client_id (str): Идентификатор клиента
        seller_token (str): Токен продавца

    Returns:
        list: Возвращает список артикулов товаров

    Examples:
        >>> client_id = "your_client_id"
        >>> seller_token = "your_seller_token"
        >>> get_offer_ids(client_id, seller_token)
        ["12345", "12346", ...]
        
    """
    last_id = ""
    product_list = []
    while True:
        some_prod = get_product_list(last_id, client_id, seller_token)
        product_list.extend(some_prod.get("items"))
        total = some_prod.get("total")
        last_id = some_prod.get("last_id")
        if total == len(product_list):
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer_id"))
    return offer_ids


def update_price(prices: list, client_id, seller_token):
    """Обновить цены товаров
    
    Args:
        prices (list): Список словарей с информацией о цене товара
        client_id (str): Идентификатор клиента
        seller_token (str): Токен продавца

    Returns:
        dict: Приходит ответ от сервера с ифнормацией о новых ценах

    Raises:
        requests.exceptions.HTTPError: Если HTTP-запрос завершился неудачно

    Examples:
        >>> prices = [{"currency_code": "RUB", "offer_id": "12345", "price": "1000", ...}, ...]
        >>> update_price(prices, client_id, seller_token)
        {"result": {...}, ...}
        
    """
    url = "https://api-seller.ozon.ru/v1/product/import/prices"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"prices": prices}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def update_stocks(stocks: list, client_id, seller_token):
    """Обновить остатки
    
    Args:
        stocks (list): Список словарей с информацией об остатках
        client_id (str): Идентификатор клиента
        seller_token (str): Токен продавца

    Returns:
        dict: Приходит ответ от сервера с информацией об обновлённых остатках

    Raises:
        requests.exceptions.HTTPError: Если HTTP-запрос завершился неудачно

    Examples:
        >>> stocks = [{"offer_id": "12345", "stock": 100}, ...]
        >>> update_stocks(stocks, client_id, seller_token)
        {"result": {...}, ...}
        
    """
    url = "https://api-seller.ozon.ru/v1/product/import/stocks"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"stocks": stocks}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def download_stock():
    """Скачать файл ostatki с сайта casio
    
    Returns:
        list: Список словарей с информацией об остатках

    Raises:
        requests.exceptions.HTTPError: Если HTTP-запрос завершился неудачно
        zipfile.BadZipFile: Если файл не является ZIP-архивом

    Examples:
        >>> download_stock()
        [{"Код": "123456", "Количество": "5", ...}, ...]
        
    """
    # Скачать остатки с сайта
    casio_url = "https://timeworld.ru/upload/files/ostatki.zip"
    session = requests.Session()
    response = session.get(casio_url)
    response.raise_for_status()
    with response, zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(".")
    # Создаем список остатков часов:
    excel_file = "ostatki.xls"
    watch_remnants = pd.read_excel(
        io=excel_file,
        na_values=None,
        keep_default_na=False,
        header=17,
    ).to_dict(orient="records")
    os.remove("./ostatki.xls")  # Удалить файл
    return watch_remnants


def create_stocks(watch_remnants, offer_ids):
    """Создать список остатков для обновления

    Args:
        watch_remnants (list): Список словарей с информацией об оставшихся часов
        offer_ids (list): Список артикулов товаров

    Returns:
        list: Список словарей с информацией об остатках

    Examples:
        >>> create_stocks(watch_remnants, offer_ids)
        [{"offer_id": "123456", "stock": 50}, ...]
        
    """
    # Уберем то, что не загружено в seller
    stocks = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append({"offer_id": str(watch.get("Код")), "stock": stock})
            offer_ids.remove(str(watch.get("Код")))
    # Добавим недостающее из загруженного:
    for offer_id in offer_ids:
        stocks.append({"offer_id": offer_id, "stock": 0})
    return stocks


def create_prices(watch_remnants, offer_ids):
    """Создать список цен

    Args:
        watch_remnants (list): Список словарей с информацией об оставшихся часов
        offer_ids (list): Список артикулов товаров

    Returns:
        list: Список словарей с информацией о ценах

    Examples:
        >>> create_prices(watch_remnants, offer_ids)
        [{"offer_id": "123456", "price": "5000", ...}, ...]
        
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "auto_action_enabled": "UNKNOWN",
                "currency_code": "RUB",
                "offer_id": str(watch.get("Код")),
                "old_price": "0",
                "price": price_conversion(watch.get("Цена")),
            }
            prices.append(price)
    return prices


def price_conversion(price: str) -> str:
    """Преобразовать цену. Пример: 5'990.00 руб. -> 5990
    
    Args:
        price(str): цена для преобразования
    Returns:
        str: возвращает преобразованную цену без лишних символов
    Raises:    
        TypeError: если входной параметр не является строкой
    Examples:
        >>>price = "5'990.00 руб."
        >>>price_conversion(price)
        5990
        
    """
    return re.sub("[^0-9]", "", price.split(".")[0])


def divide(lst: list, n: int):
    """Разделить список lst на части по n элементов

    Args:
        lst (list): Список для разделения
        n (int): Количество элементов в каждой части

    Returns:
        list: Список разбитый на части по n элементов

    Examples:
        >>> divide([1, 2, 3, 4, 5], 2)
        [[1, 2], [3, 4], [5]]
        
    """
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def upload_prices(watch_remnants, client_id, seller_token):
    """Загрузить цены на сайт Ozon

    Args:
        watch_remnants (list): Список словарей с информацией об оставшихся часов
        client_id (str): Идентификатор клиента
        seller_token (str): Токен продавца

    Returns:
        list: Список цен, которые были загружены

    Examples:
        >>> upload_prices(watch_remnants, client_id, seller_token)
        [{"offer_id": "123456", "price": "5000", ...}, ...]
        
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_price in list(divide(prices, 1000)):
        update_price(some_price, client_id, seller_token)
    return prices


async def upload_stocks(watch_remnants, client_id, seller_token):
    """Загрузить остатки на сайт Ozon

    Args:
        watch_remnants (list): Список словарей с информацией об оставшихся часов
        client_id (str): Идентификатор клиента
        seller_token (str): Токен продавца

    Returns:
        tuple: Кортеж, содержащий список остатков и список обновленных остатков

    Examples:
        >>> upload_stocks(watch_remnants, client_id, seller_token)
        (not_empty, stocks)
    """
    offer_ids = get_offer_ids(client_id, seller_token)
    stocks = create_stocks(watch_remnants, offer_ids)
    for some_stock in list(divide(stocks, 100)):
        update_stocks(some_stock, client_id, seller_token)
    not_empty = list(filter(lambda stock: (stock.get("stock") != 0), stocks))
    return not_empty, stocks


def main():
    env = Env()
    seller_token = env.str("SELLER_TOKEN")
    client_id = env.str("CLIENT_ID")
    try:
        offer_ids = get_offer_ids(client_id, seller_token)
        watch_remnants = download_stock()
        # Обновить остатки
        stocks = create_stocks(watch_remnants, offer_ids)
        for some_stock in list(divide(stocks, 100)):
            update_stocks(some_stock, client_id, seller_token)
        # Поменять цены
        prices = create_prices(watch_remnants, offer_ids)
        for some_price in list(divide(prices, 900)):
            update_price(some_price, client_id, seller_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()
