beets-artistcountry
===================

Beets plugin to retrieve the country of an artist from Musicbrainz.

Install
-------

To install, use `pip` ::

    $> pip install git+https://github.com/djhibee/beets-artistcountry

Finally, add `artistcountry` to the `plugins` section of your beets config file, creating it if it doesn't exist:

    plugins:
        - artistcountry

Configuration
-------------
'additionalArtistDirs' let you add additional folders to manually look for artist country in artist folder paths with this pattern: "$artistName ($country_code)". Ex: "Ben Harper (US)".

    artistcountry:
      additionalArtistDirs:
        - "/Music/dossier_1"
        - "/Music2/dossier_2"

How it works
------------
Embedd https://github.com/ctrueden/beets-artistcountry caching improvements:
implement a two-tier caching system to minimize MusicBrainz API calls:
- JSON cache (~/.config/beets/artistcountry.json) stores per-artist results
- Flexible attributes store per-item results in beets database
- Each artist is queried from MusicBrainz at most once

- Add `beet artistcountry` command to populate missing fields
- Template field computes on-demand, command persists to database

Architecture:
- Template field: Shows cached/computed values without side effects
- Command: Explicitly populates and persists flexible attributes
- Cache survives beets restarts, flexible attributes survive cache clearing


How to use it
-------------

You can now use the template field `artist_country` to build your path in your
audio library. Here is an example to do this in your configuration file ::

    paths:
        defaults:
            $albumartist ($artist_country)/[$year] $album%aunique{}/$track $title

Now the path for a track looks like ::

    Metallica (us)/[1984] Ride The Lightning/04 Fade To Black.mp3

	
