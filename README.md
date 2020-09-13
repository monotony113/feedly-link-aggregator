# feedly-link-aggregator

A Scrapy project for collecting hyperlinks from RSS feeds using Feedly's [Streams API](https://developer.feedly.com/v3/streams/).

**Note⚠: This project provides a way to quickly aggregate resources such as images in an RSS feed**
**for purposes such as archival work. If you are only looking to browse a feed and/or download a few things,**
**it's more appropriate (and friendly) to use [Feedly](https://feedly.com) directly.**

## Contents

- [Documentation](#documentation)
    - [Crawling](#crawling)
    - [Presets](#presets)
    - [Exporting](#exporting)
    - [Cluster spider](#cluster-spider)
- [Changelog](#changelog)
- [Notes](#notes)

## Quick usage

```bash
> git clone https://github.com/monotony113/feedly-link-aggregator.git
> cd feedly-link-aggregator
```

You'll need at least Python 3.7 (project written using Python 3.8.1).

Install dependencies:

```bash
> python3 -m pip install -r requirements.txt
```

Then start crawling:

```bash
> scrapy crawl feed -a feed='<url>' -a output='<dir>'
```

where `<url>` is the URL to your RSS feed, and `<dir>` is the directory where scraped data and temporary files will be saved.
For example,

```bash
> scrapy crawl feed -a feed="https://xkcd.com/atom.xml" -a output=instance/xkcd/
```

After it's finished, run the following to list all external links found in webpage data provided by Feedly:

```bash
> python -m feedly export urls -i '<dir>'
```

where `<dir>` is the same directory.

## Documentation

**![#f03c15](https://placehold.it/12/f06073/000000?text=+) This version (v0.10.1) has command syntax that is different from previous versions.**

### Crawling

```bash
> scrapy crawl <spider> -a feed='<url>' -a output='<dir>' [-a additional options...]
```

Currently available spiders are `feed` and `cluster`. `feed` crawls a single feed; [`cluster`](#cluster-spider) begins with a single feed
but attempts to further explore websites that are mentioned in the beginning feed.

Each spider option is specified using the `-a` option followed by a `key=value` pair.

### Presets

In addition to specifying options via the command line, you can also specify a preset.

```bash
> scrapy crawl <spider> -a preset='<path-to-file>'
```

A preset is a just a Python script whose top-level variable names and values are used as key-value pairs to populate
the spider config:

```python
from datetime import datetime
FEED = 'https://xkcd.com/atom.xml'
OUTPUT = f'instance/xkcd-{datetime.now()}'
...
```

Only variables whose names contain only uppercase letters, numbers and underscores will be used.

Presets also let you define more complex behaviors, such as URL filtering, since you can define functions and mappings.

For a list of supported options, see [`presets/example.py`](./presets/example.py). Options that are
simple string/integer values can also be specified on the command line with a case-insensitive key, in which case they take
precedence over the ones defined in a preset.

### Exporting

```bash
> python -m feedly export <topic> -i '<dir>'
```

Currently `<topic>` can be

- `urls`: Export URLs as plain-text or CSV files.
- `graph`: Represent URLs and their relations using a graph data structure (exported as GraphML files).

**![#56b6c2](https://placehold.it/12/56b6c2/000000?text=+) Example: Tumblr GIFs**

```bash
python -m feedly export urls -i data \
  --include tag is img \
  --include source:netloc under tumblr.com \
  --include target:netloc under media.tumblr.com \
  --include target:path endswith .gif \
  --include published:year lt 2017 \
  --output "%(feed:netloc)s/%(published:year)d%(published:month)02d.txt"
```

This command will select

- all image URLs that end with `.gif`
- pointing to domains under `media.tumblr.com` (Tumblr CDN servers)
- from posts before 2017
- found on all crawled subdomains of `tumblr.com` (such as `staff.tumblr.com`),

export them, and sort them into folders and files based on

- the source domain name (i.e. blog website)
- followed by the year and month of the date the post was published

resulting in a folder structure that looks like

    ./data/out/
        staff.tumblr.com/
            201602.txt
            201603.txt
            ...
        .../

----

For the `urls` exporter, the following features are available. Use the `-h`/`--help` option for a complete documentation:
`python -m feedly export urls --help`.

#### Output template

Instead of specifying a regular file name for the output file with the `-o` option, you can use a Python %-formatted
template string:

```python
-o "%(target:netloc).6s-%(published:year)d.txt"
```

This way, you can sort URLs from different sources and/or have different values such as domain names into different
files and even folders to your liking.

For example, with scraped data from the feed [`https://xkcd.com/atom.xml`](https://xkcd.com/atom.xml), an export command

```bash
> python -m feedly export urls -i data -o "%(feed:title)s/%(tag)s/%(target:netloc)s.csv"
```

could generate the following directory structure:

    ./data/out/
        xkcd.com/
            img/
                imgs.xkcd.com.csv
                xkcd.com.csv
                ...
            a/
                itunes.apple.com.csv
                www.barnesandnoble.com.csv
                ...

For a list of available placeholders, see the command help: `python -m feedly export urls --help`.

#### Filtering

Use the `--include`/`--exclude` (shorthands `+f`/`-f`) to specify filters:

```bash
+f source:netloc is "xkcd.com"
# URLs that are found in markups from xkcd.com
-f target:netloc is "google.com"
# URLs that are NOT pointing to google.com
+f target:path startswith "/wp-content"
# URLs whose path components begin with "/wp-content".
```

Filter options can be specified multiple times to enable multiple filters, Only URLs that pass _all_ filters are exported.

You can filter on URL components, feed and post titles, and dates published. For a list of filterable attributes (they are the
same as the naming template placeholders), see the command help: `python -m feedly export urls --help`.

### Cluster spider

Version v0.10 introduces a new spider called `cluster`. As the name suggests, this spider crawls not a single feed, but a cluster of feeds.

How it works:

1. The spider begins with a single feed, specified throught the `FEED` option.
2. As it crawls through the beginning feed, it parses the HTML markup snippets provided by Feedly, extracting URLs from them.
3. For each website it encounters, it will check to see if they exist as a valid RSS feed on Feedly, and if yes,
then it will start crawling that website too.
4. This process continues, until either
    - a depth limit is hit (specified with `-a depth_limit <depth>`, or in a preset file as `DEPTH_LIMIT`), then it will finish crawling the feeds that are
    `depth + 1` degrees removed from the starting feed, but will not expand beyond them; or
    - the spider was interrupted.

How many sites the spider can crawl will depend on whether it can find out a valid RSS feed URL from just a domain name. There are 2 ways to make it possible:
- Provide feed templates via a preset file. For example, knowing that WordPress sites provide RSS feeds through
[fixed endpoints such as `/?feed=rss` and `/feed/`](https://wordpress.org/support/article/wordpress-feeds/#finding-your-feed-url)
you can define your templates like such:

    ```python
    FEED_TEMPLATES = {
        r'.*\.wordpress\.com.*': {  # will match *.wordpress.com
            'http://%(netloc)s/?feed=rss': 100,  # number denotes precedence 
            'http://%(netloc)s/?feed=rss2': 200,
            'http://%(netloc)s/?feed=atom': 300,
            'http://%(netloc)s/feed/': 400,
            'http://%(netloc)s/feed/rdf/': 500,
            ...
        },
        ...
    }
    ```

    Then, if a WordPress site mentions another WordPress site, the spider will try each variation until it hits a valid feed on Feedly.

- Or, you may also enable the search function (`-a enable_search=True`, or in preset: `ENABLE_SEARCH = True`). This will let the spider search Feedly
for each domain name it encounters, and crawl all returned feed.

    ![#e5c07b](https://placehold.it/12/e5c07b/000000?text=+) **Warning: This is not recommended as the spider can quickly get rate-limited by Feedly.**

Cluster spider works best for sites that have predefined endpoints for RSS feeds, such as WordPress and Tumblr blogs (for which a
[preset](./presets/tumblr.py) is provided). Of course, if you can provide enough feed templates, it can work with many other sites as well.

## Changelog

- **v0.10.2**
    - _Cluster spider algorithm:_ Cluster spider now do breadth-first crawls, meaning it will crawl feeds closer to the starting feed
    to completion before crawling feeds that are further away.
- **v0.10.1**
    - **![#f03c15](https://placehold.it/12/f06073/000000?text=+) This version introduces API-breaking changes.**
    - _Command change:_ The commands for both crawling and exporting has changed. See the following two sections for details.
    - _Output:_
        - All spiders now require the output path be an available directory.
        - All spiders now persist scraped data using SQLite databases.
        - It is possible to run any of the spiders multiple times on the same output directory, scraped data are automatically
        merged and deduplicated.
    - _Presets:_ You can now use presets to maintain different sets of crawling options. Since presets are Python files, you can
    also specify complex settings, such as custom URL filtering functions, that cannot be specified on the command line.
    - _URL templates:_ The search function introduced in v0.3 is now off by default, because it is discovered that Feedly's Search API
    is a lot more sensitive to high-volume requests. Instead of relying on search, you can specify URL templates that allow the spiders
    to attempt different variations of feed URLs.
    - _New cluster spider:_ A new spider that, instead of crawling a single feed, also attempts to crawl any website mentioned in the feed's
    content that might themselves be RSS feeds, resulting in a network of sites being crawled. (It's like search engine spiders but for RSS feeds.)
    - _Export sorting and format:_ The revamped export module lets you select and sort URLs into different files. You may now export in
    both plain-text lines and CSV format.
    - _Graph export:_ You may now export link data as GraphML graphs, useful for visualization and network analysis. _Requires `python-igraph`._
    _Install with `pip install -r requirements-graph.txt`_
- **v0.3**
    - _Fuzzy search:_ it's no longer necessary to specify the full URL to the RSS feed data. Spider now uses Feedly's Search API to
    determine the correct URL. This means that you can simply specify e.g. the website's domain name, and Feedly will resolve it for you.
    In case there are multiple matches, they will be printed so that you can choose one and try again.
- **v0.1**
    - _URL filtering:_ you can now specify what URLs to include/exclude when running the `collect-urls` command. For example:
    `--include tag=a --exclude domain=secure.bank.com` will print out all URLs found on HTML `<a>` tags, except for those whose
    domains or parent domains contain "secure.bank.com".
    - _Feedly keywords:_ Feedly keyword data are now included in the crawl data, which you can use for filtering when running `collect-url`, 
    using the `feedly_keyword=` filter. Additionally, there is a new `collect-keywords` command that lists all keywords found in a crawl.

## Notes

- `feedly.com` has a `robots.txt` policy that disallows bots. Therefore, this crawler is set to disobey `robots.txt` (even though
what it is doing isn't crawling so much as it is consuming data from a publicly available API).
- The availability of the scraped data depends on Feedly. If no one has ever subscribed to the RSS feed you are
trying to crawl on Feedly, then your crawl may not yield any result.
- Similarly, the data you can crawl from Feedly are only as complete as how much Feedly has scraped your RSS feed.
- Explore the Feedly Cloud API at [developer.feedly.com](https://developer.feedly.com).

## Motivation

I started this project because I found out that Feedly caches a significant amount of data from dead Tumblr blogs :)

Basically:

1. As you may have already known, Tumblr did not actually delete most of the media files in the Great Tumblr Purge, 
but rather merely removed the posts containing them, meaning those media files are still available on the internet, 
albeit obscured behind their CDN URLs (the `**.media.tumblr.com` links).
2. Feedly differs from ordinary RSS readers in that it caches data from RSS feeds so that people who subscribe to the same 
RSS feed receive data from Feedly first instead of directly from the RSS provider when they are using Feedly.
3. Among the data that Feedly caches are HTML snippets of each page in the RSS feed, which include our Tumblr media links
–– and _Feedly doesn't seem to delete them even when the original posts are no longer available._

And so, effectively, Feedly has been acting as a huge Tumblr cache for as long as it has implemented such
a content-delivery strategy and people have been using it to subscribe to Tumblr blogs ;)

This project is however usable for any RSS blogs that Feedly has ever scraped (e.g. [`https://xkcd.com/atom.xml`](https://xkcd.com/atom.xml)),
or even other Feedly APIs (see their Streams API for details).
