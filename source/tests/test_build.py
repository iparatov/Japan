import unittest, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import build


class Hyperlink(unittest.TestCase):
    def test_formula(self):
        self.assertEqual(build.hyperlink('=HYPERLINK("https://x.y/a","Открыть")'), ('Открыть', 'https://x.y/a'))

    def test_plain(self):
        self.assertEqual(build.hyperlink('Текст'), ('Текст', None))


class Booking(unittest.TestCase):
    def test_kinds(self):
        k = build.book_kind
        self.assertEqual(k('Нет.'), 'none')
        self.assertEqual(k('Стол не бронируется. Приоритетный вход'), 'none')
        self.assertEqual(k('Да, через Tabelog или по телефону 03-6233-9633.'), 'online')
        self.assertEqual(k('На двоих — по телефону 03-6455-5263.'), 'phone')
        self.assertEqual(k('Только курс. По субботам — ¥6 600/чел.'), 'course')
        self.assertEqual(k('После 17:00 — только курс.'), 'course')
        self.assertEqual(k('Да, только стол, от 1 человека.'), 'online')


class Walk(unittest.TestCase):
    def test_walk(self):
        self.assertEqual(build.walk('4 мин от ICHIRAN'), (4, 'ICHIRAN'))
        self.assertEqual(build.walk('18 мин от Koun-tei*'), (18, 'Koun-tei'))
        self.assertEqual(build.walk(''), (None, None))


class Restaurants(unittest.TestCase):
    rows = [  # (ref, name, in_base, timed, extra)
        dict(ref=40, name='Yakiuo Ishikawa — Ginza Rinkaro', alt=False, base=None, timed=True, book='Да.', walk=''),
        dict(ref=40, name='↳ MASUMI Ginza 7-chome — план Б к Yakiuo', alt=True, base=True, timed=False, book='Да, бронь только стола.', walk='9 мин от Yakiuo'),
        dict(ref=40, name='Ginza Kagari Honten', alt=False, base=False, timed=False, book='Нет.', walk='12 мин от Yakiuo'),
        dict(ref=40, name='↳ Soranoiro Ginza Honten', alt=True, base=False, timed=False, book='Да, через Tabelog.', walk='16 мин от Kagari'),
    ]

    def test_promoted_main_and_dropped_old(self):
        g = build.rest_group(self.rows)
        self.assertEqual(g['main']['name'], 'MASUMI Ginza 7-chome')
        self.assertEqual([b['name'] for b in g['backups']], ['Ginza Kagari Honten', 'Soranoiro Ginza Honten'])

    def test_walk_only_from_current_main(self):
        g = build.rest_group(self.rows)
        self.assertTrue(all('walk' not in b for b in g['backups']))

    def test_walk_kept_when_from_main(self):
        rows = [dict(ref=14, name='ICHIRAN Shinjuku Kabukicho', alt=False, base=None, timed=True, book='Нет.', walk=''),
                dict(ref=14, name='↳ Kuramu Kabukicho — план Б к ICHIRAN', alt=True, base=False, timed=False, book='Да, онлайн.', walk='1 мин от ICHIRAN')]
        g = build.rest_group(rows)
        self.assertEqual(g['backups'][0]['walk'], 1)
        self.assertEqual(g['backups'][0]['name'], 'Kuramu Kabukicho')


class Copy(unittest.TestCase):
    def test_override_and_drop(self):
        c = build.Copy({'Короткий переход.': '', 'Приоритетная покупка часов.': 'Главная покупка дня — часы.'})
        self.assertEqual(c('Короткий переход.'), '')
        self.assertEqual(c('Приоритетная покупка часов.'), 'Главная покупка дня — часы.')
        self.assertEqual(c('—'), '')
        self.assertEqual(c('Неизвестная заметка.'), 'Неизвестная заметка.')
        self.assertEqual(c.unknown, ['Неизвестная заметка.'])

    def test_title_prefixes(self):
        t = build.clean_title
        self.assertEqual(t('Ужин: Gion Duck Noodles — план А'), 'Ужин — Gion Duck Noodles')
        self.assertEqual(t('ПЛАН Б — Ginza Kagari (Soba)'), 'Ginza Kagari (Soba)')


if __name__ == '__main__':
    unittest.main()


class BuiltData(unittest.TestCase):
    """Проверки на собранных данных (нужен src/table.xlsx)."""
    @classmethod
    def setUpClass(cls):
        import json, re
        html = build.build()
        man, names, files = build.unbundle(html)
        app = files[names[build.APP]].decode()
        cls.days = json.loads(re.search(r'^  static DAYS = (.*);$', app, re.M).group(1))
        cls.text = json.dumps(cls.days, ensure_ascii=False)
        cls.app, cls.card = app, files[names[build.CARD]].decode()
        cls.ds = next(b for b in files.values() if b.startswith(b'/* @ds-bundle')).decode()

    def test_no_service_text(self):
        bad = r'НЕ СУММИРОВАТЬ|по просьбе пользователя|по ссылке пользователя|по присланной связке|прежние часы рейса|вынесен[а-я]* в отдельную строку|из удалённого резерва|↳|ПЛАН А:|согласован|проверен[а-я]* карточк|«[^»]+ — маршруты», строка|Google Maps по'
        import re
        found = sorted(set(m.group(0) for m in re.finditer(bad, self.text)))
        self.assertEqual(found, [])

    def test_masumi_replaced_yakiuo(self):
        d = self.days[1]
        titles = [i['title'] for i in d['items']]
        self.assertTrue(any('MASUMI' in t for t in titles))
        self.assertFalse(any('Yakiuo' in t for t in titles))

    def test_every_meal_with_backups_has_names(self):
        for d in self.days:
            for it in d['items']:
                for b in it.get('backups', []):
                    self.assertNotIn('план Б к', b['name'])


class Price(unittest.TestCase):
    def test_price(self):
        p = build.price
        self.assertEqual(p('¥1 000–1 999'), '¥1 000–1 999')
        self.assertEqual(p('Отзывы: ¥20 000–29 999; заявлено ¥6 000–7 999'), '¥20 000–29 999')
        self.assertEqual(p('Заявлено ¥1 000–1 999; по отзывам ужин до ¥999'), 'до ¥999')
        self.assertEqual(p('Обед по отзывам ¥3–4 тыс.; ужин ¥4–5 тыс.'), '¥3 000–4 000')
        self.assertEqual(p('Средний чек не указан; онигири ¥330–990 за штуку'), '¥330–990')
        self.assertEqual(p('Не указан'), '')
        self.assertEqual(p('Завтрак ¥4 000'), '¥4 000')


class RowMatch(unittest.TestCase):
    def rows(self, *titles, date='31.10, сб'):
        return {i + 2: {'date': (date, None), 'title': (t, None), 'meal': ('—', None)} for i, t in enumerate(titles)}

    def test_row_shift_keeps_item(self):
        rows = self.rows('Новая строка', 'TISSOT Boutique Ginza')
        it = {'id': 'r2', 'title': 'TISSOT Boutique Ginza', 'type': 'place'}
        self.assertEqual(build.find_row(it, rows, '31.10', set()), 3)

    def test_edited_title_same_row_same_type(self):
        rows = self.rows('Ужин — MASUMI')
        rows[2]['meal'] = ('Ужин', None)
        it = {'id': 'r2', 'title': 'Ужин в Yakiuo', 'type': 'food'}
        self.assertEqual(build.find_row(it, rows, '31.10', set()), 2)

    def test_gone(self):
        rows = self.rows('Что-то другое')
        it = {'id': 'r2', 'title': 'TISSOT Boutique Ginza', 'type': 'food'}
        self.assertIsNone(build.find_row(it, rows, '31.10', set()))


class Excluded(BuiltData):
    def test_excluded_plan_b_removed(self):
        it = next(i for d in self.days for i in d['items'] if 'Gion Duck' in i['title'] and i['type'] == 'food')
        self.assertNotIn('planB', it)
        self.assertEqual(it['title'], 'Ужин — Gion Duck Noodles')


class NewRows(BuiltData):
    def test_restaurant_on_new_row(self):
        """Ресторан привязывается и к пункту, которого не было в прототипе (id n…)."""
        it = next(i for d in self.days for i in d['items'] if i['title'] == 'Ужин — Sushi Tofuro Nishi-Shinjuku 7-chome')
        self.assertTrue(it['id'].startswith('n'))
        self.assertEqual(it.get('mainName'), 'Sushi Tofuro Nishi-Shinjuku 7-chome')

    def test_restaurants_only_on_food(self):
        for d in self.days:
            for i in d['items']:
                if i.get('rest') or i.get('backups'):
                    self.assertEqual(i['type'], 'food', i['title'])


class PaletteC(BuiltData):
    """Вариант C из Color Study: цвет города на дне, кольце, линии таймлайна и «сейчас»; чипы — --primary, «Сделано» — --chart-2."""
    def test_city_on_root(self):
        self.assertIn('style="--city:{{ cityColor }};', self.app)
        self.assertIn('"kyoto": "var(--chart-5)"', self.app)

    def test_day_pill_and_ring(self):
        self.assertIn("bg: selected ? 'var(--city-pill)'", self.app)
        self.assertEqual(self.app.count('stroke:var(--city); stroke-width:6'), 2)

    def test_day_head_no_fill(self):
        self.assertIn('background:var(--surface-card); border-radius:var(--r-card); padding:18px 16px 18px 20px', self.app)

    def test_card(self):
        self.assertIn('width:1px; background:var(--city, var(--line-hairline))', self.card)
        self.assertIn("nodeBg: current ? 'var(--city, var(--primary))'", self.card)
        self.assertIn("checkBg: done ? 'var(--chart-2)'", self.card)

    def test_chip(self):
        self.assertIn("background: active ? 'var(--primary)'", self.ds)


class Bookings(BuiltData):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import json, re
        cls.book = json.loads(re.search(r'^  static BOOK = (.*);$', cls.app, re.M).group(1))

    def test_composition(self):
        titles = [b['title'] for b in self.book]
        self.assertEqual(sum(b['kind'] == 'flight' for b in self.book), 2)
        for gone in ('Koun-tei', 'Skyliner', 'Багаж'):
            self.assertFalse(any(gone in t for t in titles), gone)

    def test_every_booking_has_sender(self):
        for b in self.book:
            self.assertTrue(b.get('sender'), b['title'])

    def test_no_secrets(self):
        import json
        t = json.dumps(self.book, ensure_ascii=False)
        for s in ('PIN', '9458', '7613', '8927', 'regicard', 'mytickets', '771810581', '773115362'):
            self.assertNotIn(s, t)

    def test_every_hotel_has_map(self):
        for b in self.book:
            if b['kind'] == 'hotel':
                self.assertTrue(b.get('mapUrl', '').startswith('https://www.google.com/maps/'), b['title'])


class Cleanup(BuiltData):
    def test_no_service_lines(self):
        for src in (self.app, self.card):
            for s in ('нужна сеть', 'Откроется в Google Maps', 'появится связь', 'при наличии сети'):
                self.assertNotIn(s, src)

    def test_cond_merged(self):
        self.assertNotIn('"cond":"', self.text.replace(' ', '') .split('"planB"')[0][:0] + ''.join(
            __import__('json').dumps({k: v for k, v in it.items() if k != 'planB'}, ensure_ascii=False)
            for d in self.days for it in d['items']))

    def test_card_text(self):
        it = next(i for d in self.days for i in d['items'] if i['title'] == 'Ужин — MASUMI Ginza 7-chome')
        self.assertEqual(it['note'], '3-й этаж Ginza Lion Building.')
        kura = next(i for d in self.days for i in d['items'] if i['title'] == 'Kura Sushi Global Flagship Harajuku')
        self.assertEqual(kura['note'], 'Заранее встать в электронную очередь в приложении Kura Sushi.')

    def test_icons_offline(self):
        html = (build.DIST / 'index.html').read_text(encoding='utf-8')
        man, names, files = build.unbundle(html)
        icons = next(b for b in files.values() if b.startswith(b'window.__DS_ICONS={')).decode()
        for n in ('plane', 'hotel', 'undo-2'):
            self.assertIn('"%s":"data:image' % n, icons)


class BookingCardV2(Bookings):
    """Фиксы после разбора дизайна «Броней» (22.10)."""
    def by(self, i): return next(b for b in self.book if b['id'] == i)

    def test_no_guest_cells(self):
        for b in self.book:
            self.assertNotIn('ГОСТЕЙ', [c[0] for c in b['cells']], b['title'])

    def test_cells_by_kind(self):
        keys = lambda i: [c[0] for c in self.by(i)['cells']]
        self.assertEqual(keys('k5'), ['ОТПРАВЛЕНИЕ', 'ВАГОН', 'МЕСТА'])      # Hikari
        self.assertEqual(keys('k3'), ['ОТПРАВЛЕНИЕ', 'ПРИБЫТИЕ'])            # Fuji Excursion, мест в данных нет
        self.assertEqual(keys('k4'), ['ОТПРАВЛЕНИЕ', 'ПРИБЫТИЕ'])            # автобус
        self.assertEqual(keys('k2'), ['ВХОД'])
        self.assertEqual(keys('k1'), ['ЗАЕЗД', 'ВЫЕЗД', 'НОЧЕЙ'])
        self.assertEqual(keys('f1'), ['ВЫЛЕТ', 'ПРИЛЁТ'])

    def test_flight_cells_time_big_date_small(self):
        self.assertEqual(self.by('f1')['cells'], [['ВЫЛЕТ', '19:00', '29.10'], ['ПРИЛЁТ', '14:05', '30.10']])
        self.assertEqual(self.by('f2')['cells'], [['ВЫЛЕТ', '16:55', '09.11'], ['ПРИЛЁТ', '07:00', '10.11']])

    def test_number_label(self):
        for b in self.book:
            if b.get('bookingNo'):
                self.assertEqual(b.get('noLabel', 'Номер брони'), 'Код брони' if b['kind'] == 'flight' else 'Номер брони', b['title'])

    def test_url_labels(self):
        for b in self.book:
            if b.get('url'):
                self.assertRegex(b['urlLabel'], r'^Открыть (бронь|билеты?|QR|e-ticket) ', b['title'])

    def test_flight_segments_and_baggage(self):
        for i in ('f1', 'f2'):
            b = self.by(i)
            self.assertEqual(len(b['segments']), 2)
            self.assertTrue(b['baggage'])
            self.assertNotIn('seats', b)

    def test_outbound_group_label(self):
        self.assertEqual(self.by('f1')['groupLabel'], 'ЧТ, 29.10 → ПТ, 30.10')

    def test_sender_one_line(self):
        for b in self.book:
            self.assertRegex(b['sender'], r'^[^·]+ · \d\d\.\d\d( · «[^»]+»)?$', b['title'])

    def test_hotel_show(self):
        for i in ('k1', 'k6', 'k11'):
            self.assertEqual(self.by(i)['show'], 'Паспорта обоих и номер брони')

    def test_copy_is_icon_button(self):
        self.assertIn('aria-label="{{ b.copyAria }}"', self.app)
        self.assertNotIn('{{ b.copyLabel }}', self.app)


class SenderCopy(Bookings):
    def test_sender_copy_button(self):
        self.assertIn('aria-label="{{ b.senderAria }}"', self.app)
        self.assertIn('onClick="{{ b.copySender }}"', self.app)
