from beets.plugins import BeetsPlugin
from beets import ui, config
from beets.dbcore import types
import musicbrainzngs
import json
import os
from datetime import datetime
import re

# Configure MusicBrainz client
musicbrainzngs.set_useragent("beets-artistcountry-plugin", "1.0")

class CountryPlugin(BeetsPlugin):
	
    item_types = {'artist_country': types.STRING}
    
    def __init__(self):
        super(CountryPlugin, self).__init__()
        self.artist_country = None
        self.template_fields['artist_country'] = _tmpl_country
        self.cache_file = os.path.join(config.config_dir(), 'artistcountry.json')
        self._cache = None
        self._log.debug("Plugin instanciated")
    
    def commands(self):
        def artistcountry_func(lib, opts, args):
            """Populate artist_country for items matching the query."""
            query = args if args else []
            items = lib.items(query)

            self._log.info(f'Processing {len(items)} items...')
            updated = 0

            for item in items:
                # Check if artist_country is already set in flexible attributes
                if not item._values_flex.get('artist_country'):
                    country = self.get_artist_country(item)
                    if country:
                        item['artist_country'] = country
                        item.store()
                        updated += 1
                        self._log.debug(f'Set artist_country={country} for {item.artist} - {item.title}')
                else:
                    country = item['artist_country']
                    self._log.debug(f'Artist country already set as flex value: {country}')

            self._log.info(f'Updated {updated} items with artist_country')

        artistcountry_cmd = ui.Subcommand('artistcountry', help='populate artist_country fields')
        artistcountry_cmd.func = artistcountry_func
        return [artistcountry_cmd]
    
    
    def load_cache(self):
        """Load artist country cache from JSON file."""
        if self._cache is not None:
            return self._cache
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    self._cache = json.load(f)
            else:
                self._cache = {}
        except (json.JSONDecodeError, IOError) as e:
            self._log.warning(f'Error loading artist country cache: {e}')
            self._cache = {}

        return self._cache
        
    def save_cache(self):
        """Save artist country cache to JSON file."""
        if self._cache is None:
            return
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)

            with open(self.cache_file, 'w') as f:
                json.dump(self._cache, f, indent=2)
        except IOError as e:
            self._log.warning(f'Error saving artist country cache: {e}')
        
    def get_artist_country(self, item):
        item_types = {'country': types.STRING}
        artistName = item.get('albumartist')
        country = None
        # we use albumartistid instead of artist to be sure all songs from an album get the same result
        mb_albumartistid = item.get('mb_albumartistid')  
        self._log.debug("debug1")
        cache = self.load_cache()
        
        try:  
            """Get artist country, using cache first, then MusicBrainz."""
            if not mb_albumartistid or len(mb_albumartistid) != 36 or mb_albumartistid.count('-') != 4:
                # fallback on artist name, as cache also store country for its
                mb_albumartistid = artistName
                # Check cache first
                if artistName and artistName in cache and cache[artistName].get('country'):
                    self._log.debug("Return artist country from cache by name")
                    return cache[mb_albumartistid].get('country')
                country = _country_from_existing_artists(artistName)
                # we dont necessary have mb Ids (deezer metadata) so we search them. Cons is that we often need to select manually because several results so a bit useless
                #self._log.debug("no mbalbumartistid, search by artist name")
                #tmp = musicbrainzngs.search_artists(query=f'artist:"{artistName}"' , strict=True)
                #if len(tmp['artist-list']) > 1:
                #   self._log.debug("several artist matched...")
                #   for artistProposal in tmp['artist-list']:
                #      print("{name}: {id}".format(name=artistProposal["name"], id=artistProposal['id']))
                #   mb_albumartistid = input("Select mb artistid {id} corresponding in musicbrainz to {artist1}:".format(id=tmp['artist-list'][0]['id'], artist1=artistName))
                #else:
                #      mb_albumartistid = tmp['artist-list'][0]['id']
                #self._log.debug(f"mb_albumartistid: {mb_albumartistid}")
            else: 
                # Check cache first
                if mb_albumartistid in cache and cache[mb_albumartistid].get('country'):
                    self._log.debug("Return artist country from cache by id")
                    return cache[mb_albumartistid].get('country')
                # Query MusicBrainz
                try:
                    artist_item = musicbrainzngs.get_artist_by_id(mb_albumartistid)
                    artist = artist_item.get('artist')
                    country = artist.get('country', '')

                    if not country and 'area' in artist:
                        country = _country_from_area(artist['area'])
                
                except Exception as e:
                    self._log.debug(f"Error fetching country for artist by mb_albumartistid {mb_albumartistid}: {e}")
                    
        except Exception as e:
                    self._log.debug(f"Unexpected Error fetching country: {e}")
        finally: 
            if not country:
                 # Try to find artist country from library path if not already done
                 country = _country_from_existing_artists(artistName)
            if country:
                 country = country.upper()
                 # Cache the result if not empty
                 cache[mb_albumartistid] = {
                    'country': country,
                    'cached': datetime.now().isoformat(),
                    'name': artistName
                 }
                 self._cache = cache
                 self.save_cache()
            return country if country else ''
   
# Global plugin instance for template function access
_plugin_instance = None	

def get_plugin_instance():
    global _plugin_instance
    if _plugin_instance is None:
        _plugin_instance = CountryPlugin()
    return _plugin_instance
    
@CountryPlugin.template_field('artist_country')
def _tmpl_country(item):
    """Template field that returns artist_country, caching and storing result."""
    # Check if already stored in flexible attributes
    if item._values_flex.get('artist_country'):
        return item._values_flex['artist_country']
    # Get from cache/API
    plugin = get_plugin_instance()
    _plugin_instance._log.debug("artist_country CALLED")
    country = plugin.get_artist_country(item)

    # Store in flexible attributes for persistence
    if country:
        item['artist_country'] = country
        # Note: We don't call item.store() here to avoid side effects during template rendering

    return country

def _country_from_area(area):
    countries = _find_top_area(area)
    return countries[0]


def _find_top_area(area):
    new_area = get_area_by_id(area['id'], includes=['area-rels'])
    new_area = [
        a['area'] for a in new_area['area']['area-relation-list']
        if a.get('direction', '') == 'backward'
    ]

    if not new_area:
        return area['iso-3166-1-code-list']

    area = new_area[0]
    if _has_country_iso_code(area):
        return area['iso-3166-1-code-list']

    return _find_top_area(area)


def _has_country_iso_code(area):
    return area['type'] == "Country" and "iso-3166-1-code-list" in area
    
def _country_from_existing_artists(name):
	plugin = get_plugin_instance()
	rootMusicFolder = "/volume1/Music/music/"
	try:
		country = ''
		# artist directory structure is "ArtistName (XX)"
		pattern="^"+ name + " \(([A-Z]{2})\)$"
		print(pattern)
		print(name)
		for root, dirs, files in os.walk(rootMusicFolder):
			for d in dirs:
				x : None
				try:
				   x = re.search(pattern, d)
				except Exception as e:
				   _plugin_instance._log.debug(f"search excpetion: {e}")
				if x:
					country = x.group(1)
					print("YES! We found artist country from directories! The country is %s" % country)
					break
			break
	except Exception as e:
		self._log.debug(f"Error fetching country for artist from music library: {e}")
	finally:
		if not country:
			country = _country_from_user_input(name)
		return country
	
def _country_from_user_input(name):
	country = input(f"Enter country for artist {name} (not found in musicbrainz nor music library):")
	return country
