import re
import logging
import requests
import requests_cache


from bs4 import BeautifulSoup
from tqdm import tqdm
from urllib.parse import urljoin


from outputs import control_output
from utils import get_response, find_tag
from constants import BASE_DIR, MAIN_DOC_URL, MAIN_PEP_URL
from configs import configure_argument_parser, configure_logging


def pep(session):
    response = session.get(MAIN_PEP_URL)
    response.encoding = 'utf-8'
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    tables = soup.find_all('table', {'class': re.compile(r'pep.+')})
    main_dict = {}
    result_dict = {'A': 0,
                   'D': 0,
                   'F': 0,
                   'P': 0,
                   'R': 0,
                   'S': 0,
                   'W': 0,
                   'Amount': 0}
    for i in tables:
        for j in i.tbody.find_all('tr'):
            try:
                if len(j.find('abbr').text) > 1:
                    status = find_tag(j, 'abbr').text[-1]
                else:
                    status = None
            except AttributeError:
                status = None
            link_pep = find_tag(j, 'a')['href']
            main_dict[link_pep] = status
    for link in tqdm(main_dict):
        version_link = urljoin(MAIN_PEP_URL, link)
        response = requests.get(version_link)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, features='lxml')
        status_on_page = find_tag(soup, 'abbr').text[0]
        if main_dict[link] is not None:
            if main_dict[link] == status_on_page:
                result_dict[status_on_page] += 1
            else:
                logging.info(
                    f'Выявлено несоответвие статуса,'
                    f'статус на главной странице - *{main_dict[link]}*,'
                    f'статус на странице PEP - *{status_on_page}*,'
                    f'PEP: {version_link}')
                result_dict[status_on_page] += 1
        else:
            result_dict[status_on_page] += 1
    result_dict['Amount'] += sum(result_dict.values())
    return [data for data in result_dict.items()]


def whats_new(session):
    whats_new_url = urljoin(MAIN_DOC_URL, 'whatsnew/')
    response = session.get(whats_new_url)
    response.encoding = 'utf-8'
    response = get_response(session, whats_new_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, features='lxml')
    main_div = find_tag(soup, 'section', attrs={'id': 'what-s-new-in-python'})
    div_with_ul = find_tag(main_div, 'div', attrs={'class': 'toctree-wrapper'})
    sections_by_python = div_with_ul.find_all(
        'li', attrs={'class': 'toctree-l1'})
    results = [('Ссылка на статью', 'Заголовок', 'Редактор, Автор')]
    for section in tqdm(sections_by_python):
        version_a_tag = find_tag(section, 'a')
        href = version_a_tag['href']
        version_link = urljoin(whats_new_url, href)
        response = requests.get(version_link)
        response.encoding = 'utf-8'
        if response is None:
            continue
        soup = BeautifulSoup(response.text, features='lxml')
        h1 = find_tag(soup, 'h1')
        dl = find_tag(soup, 'dl')
        dl_text = dl.text.replace('\n', ' ')
        results.append((version_link, h1.text, dl_text))
    return results


def latest_versions(session):
    response = session.get(MAIN_DOC_URL)
    response.encoding = 'utf-8'
    response = get_response(session, MAIN_DOC_URL)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    sidebar = find_tag(soup, 'div', attrs={'class': 'sphinxsidebarwrapper'})
    ul_tags = sidebar.find_all('ul')
    for ul in ul_tags:
        if 'All versions' in ul.text:
            a_tags = ul.find_all('a')
            break
    else:
        raise Exception('Ничего не нашлось')

    results = [('Ссылка на документацию', 'Версия', 'Статус')]
    pattern = r'Python (?P<version>\d\.\d+) \((?P<status>.*)\)'
    for a_tag in a_tags:
        link = a_tag['href']
        text_match = re.search(pattern, a_tag.text)
        if text_match is not None:
            version, status = text_match.groups()
        else:
            version, status = a_tag.text, ''
        results.append(
            (link, version, status)
        )
    return results


def download(session):
    downloads_url = urljoin(MAIN_DOC_URL, 'download.html')
    response = session.get(downloads_url)
    response.encoding = 'utf-8'
    response = get_response(session, downloads_url)
    if response is None:
        return
    soup = BeautifulSoup(response.text, 'lxml')
    main_tag = find_tag(soup, 'div', {'role': 'main'})
    table_tag = find_tag(main_tag, 'table', {'class': 'docutils'})
    pdf_a4_tag = find_tag(
        table_tag, 'a', {'href': re.compile(r'.+pdf-a4\.zip$')})
    pdf_a4_link = pdf_a4_tag['href']
    archive_url = urljoin(downloads_url, pdf_a4_link)
    filename = archive_url.split('/')[-1]
    downloads_dir = BASE_DIR / 'downloads'
    downloads_dir.mkdir(exist_ok=True)
    archive_path = downloads_dir / filename
    response = requests.get(archive_url)
    with open(archive_path, 'wb') as file:
        file.write(response.content)
    logging.info(f'Архив был загружен и сохранён: {archive_path}')


MODE_TO_FUNCTION = {
    'whats-new': whats_new,
    'latest-versions': latest_versions,
    'download': download,
    'pep': pep,
}


def main():
    configure_logging()
    logging.info('Парсер запущен!')
    arg_parser = configure_argument_parser(MODE_TO_FUNCTION.keys())
    args = arg_parser.parse_args()
    logging.info(f'Аргументы командной строки: {args}')

    session = requests_cache.CachedSession()
    if args.clear_cache:
        session.cache.clear()

    parser_mode = args.mode
    results = MODE_TO_FUNCTION[parser_mode](session)
    if results is not None:
        control_output(results, args)
    logging.info('Парсер завершил работу.')


if __name__ == '__main__':
    main()
