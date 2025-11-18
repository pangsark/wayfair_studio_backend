import requests
from bs4 import BeautifulSoup
import json


def scrape():
    url = 'https://www.wayfair.com/furniture/pdp/corrigan-studio-jeses-minimore-modern-style-etta-843-mid-century-modern-design-sofa-w009604355.html?piid=1645519654'

    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    print(soup)


if __name__ == '__main__':
   scrape()