import os, requests, logging, datetime, re, html, bs4, dateutil.parser
import wsgiref.util
import wsgiref.handlers
import wsgiref.simple_server

from bs4 import BeautifulSoup


class Event:
	def __init__(self, start: datetime.datetime, end: datetime.datetime,
			title: str, location: str, notes: str):
		self.start = start
		self.end = end
		self.title = title
		self.location = location
		self.notes = notes
	
	def iter_lines(self):
		yield 'BEGIN:VEVENT'
		yield 'DTSTART:{}'.format(self._encode_time(self.start))
		yield 'DTEND:{}'.format(self._encode_time(self.end))
		yield 'SUMMARY:{}'.format(self._encode_string(self.title))
		yield 'LOCATION:{}'.format(self._encode_string(self.location))
		yield 'DESCRIPTION:{}'.format(self._encode_string(self.notes))
		yield 'END:VEVENT'
	
	@classmethod
	def _encode_time(cls, value: datetime.datetime):
		return value.strftime('%Y%m%dT%H%M%SZ')
	
	@classmethod
	def _encode_string(cls, value: str):
		return re.sub('([\\\\\n,;])', '\\\\\\1', value)


class Calendar:
	def __init__(self, events: list):
		self.events = events
	
	def iter_lines(self):
		yield 'BEGIN:VCALENDAR'
		yield 'VERSION:2.0'
		yield 'CALSCALE:GREGORIAN'
		
		for i in self.events:
			yield from i.iter_lines()
		
		yield 'END:VCALENDAR'


def get_calendar():
	logging.info('Requesting schedule ...')
	
	result = requests.get('https://gamesdonequick.com/schedule')
	
	assert result.headers['content-type'].split(';', 1)[
		       0].strip().lower() == 'text/html'
	
	return result.text


def parse_duration(string):
	h, m, s = map(int, string.split(':'))
	
	return datetime.timedelta(hours = h, minutes = m, seconds = s)


def get_cell_contents(row):
	return [i.text for i in row.find_all('td')]


def parse_entries(text: str):
	soup = BeautifulSoup(text, 'html.parser')

	schedule_table = soup.find(id='runTable')

	def iter_entries():
		for row in schedule_table.tbody.find_all('tr'):
			if 'second-row' not in row.get('class', []):
				second_row = row.find_next_sibling('tr')

				if second_row:
					start_str, name, runners, setup = get_cell_contents(row)
					estimate_str, category = get_cell_contents(second_row)

					start = dateutil.parser.parse(start_str)
					estimate = parse_duration(estimate_str)
					notes = '' # Where is this?

					if category:
						title = '{} ({})'.format(name, category)
					else:
						title = name

					yield Event(start, start + estimate, title, runners, notes)

	return Calendar(list(iter_entries()))


def get_vcard():
	calender = parse_entries(get_calendar())
	
	return ''.join(i + '\n' for i in calender.iter_lines())


def app(environ, start_response):
	wsgiref.util.setup_testing_defaults(environ)
	
	start_response(
		'200 OK',
		[('content-type', 'text/calendar; charset=utf-8')])
	
	return [get_vcard().encode()]


def main():
	logging.basicConfig(level = logging.INFO)
	# parse_entries(get_calendar())
	
	if 'PATH_INFO' in os.environ:
		wsgiref.handlers.CGIHandler().run(app)
	else:
		httpd = wsgiref.simple_server.make_server('', 8000, app)
		logging.info("Serving on port 8000...")
		httpd.serve_forever()


main()
