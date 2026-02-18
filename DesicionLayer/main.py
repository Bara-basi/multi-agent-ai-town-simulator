from model.definitions import Catalog
from runtime.load_data import load_catalog


if __name__ == '__main__':
    catalog:Catalog = load_catalog()
    