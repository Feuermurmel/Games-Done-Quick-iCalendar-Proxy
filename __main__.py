import os, requests, logging, datetime, re, html
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
		yield 'DTSTART:{}'.format(self._encode_time(self.start))
		yield 'DTEND:{}'.format(self._encode_time(self.end))
		yield 'SUMMARY:{}'.format(self._encode_string(self.title))
		yield 'LOCATION:{}'.format(self._encode_string(self.location))
		yield 'DESCRIPTION:{}'.format(self._encode_string(self.notes))
		yield 'END:VEVENT'
	
	@classmethod
	def _encode_time(cls, value : datetime.datetime):
		return value.strftime('%Y%m%dT%H%M%SZ')
	
	@classmethod
	def _encode_string(cls, value : str):
		return re.sub('([\\\\\n,;])', '\\\\\\1', value)


class Calendar:
	def __init__(self, events : list):
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
			contents = { j: html.unescape(i.group(j).strip()) for j in parts }
			
			start = parse_date(contents['start'])
			name = contents['name']
			runners = contents['runners']
			estimate = parse_duration(contents['estimate'])
			category = contents['category']
			setup = parse_duration(contents['setup'])
			notes = contents['notes']
			
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
