import datetime
import logging.config
from environs import Env
from seller import download_stock

import requests

from seller import divide, price_conversion

logger = logging.getLogger(__file__)


def get_product_list(page, campaign_id, access_token):
    """Получить список товаров с Яндекс Маркета

    Args:
        page (str): Страница на котором получен последний товар
        campaign_id (str): Идентификатор кампании
        access_token (str): Токен продавца

    Returns:
        dict: Возвращает словарь содержащий список товаров
        
    Raises:
        requests.exceptions.HTTPError: Если HTTP-запрос завершился с ошибкой
        ValueError: Если обязательные параметры не переданы или имеют неверный тип

    Examples:
        >>> get_product_list("123", "campaign_456", "access_token_789")
        [{'offer': {'shopSku': 'sku_1'}, ...}, {'offer': {'shopSku': 'sku_2'}, ...}]  
        
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {
        "page_token": page,
        "limit": 200,
    }
    url = endpoint_url + f"campaigns/{campaign_id}/offer-mapping-entries"
    response = requests.get(url, headers=headers, params=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def update_stocks(stocks, campaign_id, access_token):
    """Обновить остатки

    Args:
        stocks (list): Список словарей с информацией об остатках
        campaign_id (str): Идентификатор кампании
        access_token (str): Токен продавца

    Returns:
        dict: Приходит ответ от сервера с информацией об обновлённых остатках

    Raisis:
        requests.exceptions.HTTPError: Если HTTP-запрос завершился неудачно

    Examples:
        >>> stocks = {
                    "sku": str(watch.get("Код")),
                    "warehouseId": warehouse_id,
                    "items": [
                        {
                            "count": stock,
                            "type": "FIT",
                            "updatedAt": date,
                        }
                    ],
                }
        >>> update_stocks(stocks, "campaign_456", "access_token_789")
        {'status': 'success', ...}
        
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"skus": stocks}
    url = endpoint_url + f"campaigns/{campaign_id}/offers/stocks"
    response = requests.put(url, headers=headers, json=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object


def update_price(prices, campaign_id, access_token):
    """Обновить цены товаров

    Args:
        prices (list): Список словарей с информацией о цене товара
        campaign_id (str): Идентификатор кампании
        access_token (str): Токен доступа для аутентификации

    Returns:
        dict: Приходит ответ от сервера с ифнормацией о новых ценах
        
    Raises:
        requests.exceptions.HTTPError: Если HTTP-запрос завершился неудачно

    Examples:
        >>> prices = [
                {
                    "id": "sku_1",
                    "price": {
                        "value": 1000,
                        "currencyId": "RUR"
                    }
                },
                ...
            ]
        >>> update_price(prices, "campaign_456", "access_token_789")
        {'status': 'success', ...}
        
    """
    endpoint_url = "https://api.partner.market.yandex.ru/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Host": "api.partner.market.yandex.ru",
    }
    payload = {"offers": prices}
    url = endpoint_url + f"campaigns/{campaign_id}/offer-prices/updates"
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    response_object = response.json()
    return response_object


def get_offer_ids(campaign_id, market_token):
    """Получить артикулы товаров Яндекс маркета

    Args:
        campaign_id (str): Идентификатор кампании
        market_token (str): Токен продавца

    Returns:
        list: Возвращает список артикулов товаров

    Examples:
        >>> get_offer_ids("campaign_456", "market_token_789")
        ["123456", "123457", ...]
        
    """
    page = ""
    product_list = []
    while True:
        some_prod = get_product_list(page, campaign_id, market_token)
        product_list.extend(some_prod.get("offerMappingEntries"))
        page = some_prod.get("paging").get("nextPageToken")
        if not page:
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer").get("shopSku"))
    return offer_ids


def create_stocks(watch_remnants, offer_ids, warehouse_id):
    """Создать список остатков для обновления

    Args:
        watch_remnants (list): Список словарей с информацией об оставшихся часов
        offer_ids (list):  Список артикулов товаров
        warehouse_id (int): Идентификатор склада

    Returns:
        list: Список словарей с информацией об остатках

    Examples:
        >>> create_stocks([...], ["sku_1", "sku_2"], 1)
        [
            {
                "sku": "sku_1",
                "warehouseId": 1,
                "items": [
                    {
                        "count": 100,
                        "type": "FIT",
                        "updatedAt": "2023-10-01T12:00:00Z"
                    }
                ]
            },
            ...
        ]
        
    """
    # Уберем то, что не загружено в market
    stocks = list()
    date = str(datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z")
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append(
                {
                    "sku": str(watch.get("Код")),
                    "warehouseId": warehouse_id,
                    "items": [
                        {
                            "count": stock,
                            "type": "FIT",
                            "updatedAt": date,
                        }
                    ],
                }
            )
            offer_ids.remove(str(watch.get("Код")))
    # Добавим недостающее из загруженного:
    for offer_id in offer_ids:
        stocks.append(
            {
                "sku": offer_id,
                "warehouseId": warehouse_id,
                "items": [
                    {
                        "count": 0,
                        "type": "FIT",
                        "updatedAt": date,
                    }
                ],
            }
        )
    return stocks


def create_prices(watch_remnants, offer_ids):
    """Создать список цен

    Args:
        watch_remnants (list): Список словарей с информацией об оставшихся часов
        offer_ids (list): Список артикулов товаров

    Returns:
        list: Список словарей с информацией о ценах

    Examples:
        >>> create_prices([...], ["sku_1", "sku_2"])
        [
            {
                "id": "sku_1",
                "price": {
                    "value": 1000,
                    "currencyId": "RUR"
                }
            },
            ...
        ]
        
    """
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "id": str(watch.get("Код")),
                # "feed": {"id": 0},
                "price": {
                    "value": int(price_conversion(watch.get("Цена"))),
                    # "discountBase": 0,
                    "currencyId": "RUR",
                    # "vat": 0,
                },
                # "marketSku": 0,
                # "shopSku": "string",
            }
            prices.append(price)
    return prices


async def upload_prices(watch_remnants, campaign_id, market_token):
    """Загрузить цены на Яндекс Маркет.

    Args:
        watch_remnants (list): Список словарей с информацией об оставшихся часов
        campaign_id (str): Идентификатор кампании
        market_token (str): Токен продавца

    Returns:
        list: Список цен, которые были загружены

    Examples:
        >>> upload_prices(watch_remnants, "campaign_456", "market_token_789")
        [
            {
                "id": "sku_1",
                "price": {
                    "value": 1000,
                    "currencyId": "RUR"
                }
            },
            ...
        ]
        
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_prices in list(divide(prices, 500)):
        update_price(some_prices, campaign_id, market_token)
    return prices


async def upload_stocks(watch_remnants, campaign_id, market_token, warehouse_id):
    """Загрузить остатки на Яндекс Маркет

    Args:
        watch_remnants (list): Список словарей с информацией об оставшихся часов
        campaign_id (str): Идентификатор кампании
        market_token (str): Токен продавца
        warehouse_id (int): Идентификатор склада

    Returns:
        tuple: Кортеж, содержащий список непустых остатков и полный список остатков

    Examples:
        >>> upload_stocks(watch_remnants, "campaign_456", "market_token_789", 1)
        (not_empty, stocks)
        
    """
    offer_ids = get_offer_ids(campaign_id, market_token)
    stocks = create_stocks(watch_remnants, offer_ids, warehouse_id)
    for some_stock in list(divide(stocks, 2000)):
        update_stocks(some_stock, campaign_id, market_token)
    not_empty = list(
        filter(lambda stock: (stock.get("items")[0].get("count") != 0), stocks)
    )
    return not_empty, stocks


def main():
    env = Env()
    market_token = env.str("MARKET_TOKEN")
    campaign_fbs_id = env.str("FBS_ID")
    campaign_dbs_id = env.str("DBS_ID")
    warehouse_fbs_id = env.str("WAREHOUSE_FBS_ID")
    warehouse_dbs_id = env.str("WAREHOUSE_DBS_ID")

    watch_remnants = download_stock()
    try:
        # FBS
        offer_ids = get_offer_ids(campaign_fbs_id, market_token)
        # Обновить остатки FBS
        stocks = create_stocks(watch_remnants, offer_ids, warehouse_fbs_id)
        for some_stock in list(divide(stocks, 2000)):
            update_stocks(some_stock, campaign_fbs_id, market_token)
        # Поменять цены FBS
        upload_prices(watch_remnants, campaign_fbs_id, market_token)

        # DBS
        offer_ids = get_offer_ids(campaign_dbs_id, market_token)
        # Обновить остатки DBS
        stocks = create_stocks(watch_remnants, offer_ids, warehouse_dbs_id)
        for some_stock in list(divide(stocks, 2000)):
            update_stocks(some_stock, campaign_dbs_id, market_token)
        # Поменять цены DBS
        upload_prices(watch_remnants, campaign_dbs_id, market_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()
