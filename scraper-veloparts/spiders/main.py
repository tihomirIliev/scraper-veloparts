import scrapy
import pdb
import json
import pprint
from ..items import VelopartsItem
from scrapy.loader import ItemLoader


class ProductsSpider(scrapy.Spider):
    name = "products"
    allowed_domains = ['mr-bricolage.bg']
    start_urls = [
        'https://mr-bricolage.bg/bg/Instrumenti/Avto-i-veloaksesoari/Veloaksesoari/c/006008012']

    def parse(self, response):
        listOfProducts = response.css('.product-item div.product')

        for product in listOfProducts:
            linkToProduct = product.css('div.image').xpath('a/@href').get()
            product_image = product.css('div.image>a>img::attr(src)').get()

            if linkToProduct is not None:
                yield response.follow(linkToProduct, self.parse_characteristics)

        next_page = response.css(
            "ul.pagination li.pagination-next>a::attr(href)").get()
        if next_page is not None:
            yield response.follow(next_page, self.parse)

    def parse_characteristics(self, response):
        items = VelopartsItem()

        # Required elements for building the request URL for the store availability
        csrf = response.xpath(
            "//input[@name='CSRFToken']/@value").extract_first()
        cookie = response.headers.getlist("Set-Cookie")[0].decode("utf-8")
        product_id = response.xpath(
            "//div[@class='col-md-12 bricolage-code']/text()").extract_first().split(":")[1].strip()

        # Extracting the wanted items
        title = response.css('.col-md-6').xpath('//h1/text()')[0].get()
        price = response.css(
            '.col-md-12.price p::text').get().strip().replace(' лв.', '').replace(',', '.')
        classifications = [x.strip() for x in response.css(
            '.product-classifications').xpath('table/tbody/tr/td/text()').extract()]
        ean = response.xpath(
            '//*[@id="home"]/div[1]/span/text()').extract()[1].strip()
        image = response.css('.col-md-6')[1].xpath('.//div/img/@src').get()

        # Storing the wanted items
        items['title'] = title
        items['price'] = price
        items['classifications'] = classifications
        items['ean'] = ean
        items['image'] = image

        # Request for the product availability per store
        request_stock = scrapy.Request(
            method="POST",
            url="https://mr-bricolage.bg/store-pickup/{}/pointOfServices".format(product_id) +
            "?locationQuery=&cartPage=false&entryNumber=0&latitude=42.6641056&longitude=23.3233149&" +
            "CSRFToken={}".format(csrf),
            headers={
                'accept': '*/*',
                'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'x-requested-with': 'XMLHttpRequest',
                'User-Agent': ' Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/' +
                '537.36 (KHTML, like Gecko) Chrome/71.0.3578.98 Safari/537.36',
                'Cookie': cookie.split(";")[0],
            },
            callback=self.parse_stock
        )

        request_stock.meta['items'] = items
        yield request_stock

    # Extracting the information about the stock
    def parse_stock(self, response):
        items = response.meta['items']

        store_name = [n['name']
                      for n in json.loads(response.body.decode("utf-8"))['data']]
        stock_level = [s['stockLevel']
                       for s in json.loads(response.body.decode("utf-8"))['data']]

        items['store'] = store_name
        items['stock'] = stock_level

        yield items
