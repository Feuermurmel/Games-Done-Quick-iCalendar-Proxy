import os, requests, logging, datetime, re
import wsgiref.util
import wsgiref.handlers
import wsgiref.simple_server


class Event:
	def __init__(self, start : datetime.datetime, end : datetime.datetime, title : str, location : str, notes : str):
		self.start = start
		self.end = end
		self.title = title
		self.location = location
		self.notes = notes
	
	def iter_lines(self):
		yield 'BEGIN:VEVENT'
		yield 'DTSTART:{}'.format(self.start.strftime('%Y%m%dT%H%M%SZ'))
		yield 'DTEND:{}'.format(self.end.strftime('%Y%m%dT%H%M%SZ'))
		yield 'TRANSP:OPAQUE'
		yield 'SUMMARY:{}'.format(self.title)
		yield 'LOCATION:{}'.format(self.location)
		yield 'DESCRIPTION:{}'.format(self.notes)
		yield 'END:VEVENT'


class Calendar:
	def __init__(self, events : list):
		self.events = events
	
	def iter_lines(self):
		yield 'BEGIN:VCALENDAR'
		yield 'METHOD:PUBLISH'
		yield 'VERSION:2.0'
		yield 'CALSCALE:GREGORIAN'
		
		for i in self.events:
			yield from i.iter_lines()
		
		yield 'END:VCALENDAR'


def get_calendar():
	logging.info('Requesting schedule ...')
	
	result = requests.get('https://gamesdonequick.com/schedule')
	
	assert result.headers['content-type'].split(';')[0].strip().lower() == 'text/html'
	
	return result.text


def parse_date(string):
	return datetime.datetime.strptime(string, '%Y-%m-%dT%H:%M:%SZ')


def parse_duration(string):
	h, m, s = map(int, string.split(':'))
	
	return datetime.timedelta(hours = h, minutes = m, seconds = s)


def parse_entries(text : str):
	parts = 'start name runners estimate category setup notes'.split()
	
	def iter_pattern_parts():
		yield '<tr>'
		
		for i in parts:
			yield '<td(\s+class="[^"]*")?>(?P<{}>[^<]*)</td>'.format(i)
		
		yield '</tr>'
	
	pattern = '\s*'.join(iter_pattern_parts())
	
	def iter_entries():
		for i in re.finditer(pattern, re.sub('\n', ' ', text)):
			start = parse_date(i.group('start').strip())
			name = i.group('name').strip()
			runners = i.group('runners').strip()
			estimate = parse_duration(i.group('estimate').strip())
			category = i.group('category').strip()
			setup = parse_duration(i.group('setup').strip())
			notes = i.group('notes').strip()
			
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
