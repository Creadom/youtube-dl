# coding: utf-8
from __future__ import unicode_literals

import functools
import itertools
import json # debug
import operator
import re

from .common import InfoExtractor

from ..compat import (
    compat_HTTPError,
    compat_str,
    compat_urllib_request,
)

from .openload import PhantomJSwrapper

from ..utils import (
    determine_ext,
    ExtractorError,
    int_or_none,
    orderedSet,
    remove_quotes,
    str_to_int,
    urlencode_postdata,
    url_or_none,
)


class PornHubPremiumBaseIE(InfoExtractor):
    """
    PornHubBaseIE is the base class responsible for handling videos from PornHub sites
    like PornHub and PornHub Premium.
    """

    def _download_webpage_handle(self, *args, **kwargs):
        def dl(*args, **kwargs):
            return super(PornHubPremiumBaseIE, self)._download_webpage_handle(*args, **kwargs)

        webpage, urlh = dl(*args, **kwargs)

        if any(re.search(p, webpage) for p in (
                r'<body\b[^>]+\bonload=["\']go\(\)',
                r'document\.cookie\s*=\s*["\']RNKEY=',
                r'document\.location\.reload\(true\)')):
            url_or_request = args[0]
            url = (url_or_request.get_full_url()
                   if isinstance(url_or_request, compat_urllib_request.Request)
                   else url_or_request)
            phantom = PhantomJSwrapper(self, required_version='2.0')
            phantom.get(url, html=webpage)
            webpage, urlh = dl(*args, **kwargs)

        return webpage, urlh

    def _login(self, login_url, login_host, netrc_machine, requires_login=True):
        username, password = self._get_login_info()

        # Check login required
        if requires_login:
            if not username or not password:
                self.raise_login_required(
                    'A "%s" account is required'
                    % netrc_machine)

        # Return if missing auth
        if not username or not password:
            return

        # Set cookies
        self._set_cookie(login_host, 'age_verified', '1')
        self._set_cookie(login_host, 'platform', 'pc')

        # Fetch login page
        print(login_url)
        login_page = self._download_webpage(
            login_url, None, 'Downloading login page')

        # Already logged in
        if self._is_authenticated(login_page):
            return

        login_form = self._hidden_inputs(login_page)
        login_form.update({
            'username': username,
            'password': password,
        })

        response = self._download_json(
            'https://www.%s/front/authenticate' % login_host, None, 'Logging in to %s' % login_host,
            data=urlencode_postdata(login_form), headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': login_url,
            })

        # Success
        if response.get('success') == '1':
            return

        login_error = response.get('message')
        if login_error:
            raise ExtractorError('Unable to login: %s' % login_error, expected=True)

        self.report_warning('Login has probably failed')

    def _extract_count(self, pattern, webpage, name, **kwargs):
        """stub"""
        return str_to_int(self._search_regex(
            pattern, webpage, '%s count' % name, fatal=False, **kwargs))

    def _extract_video_title(self, webpage):
        """
        Read video title from page metadata.

        The video_title from flashvars contains whitespace instead of non-ASCII (see
        http://www.pornhubpremium.com/view_video.php?viewkey=1331683002), not relying on that anymore.
        """
        title = self._html_search_meta('twitter:title', webpage, default=None)

        if not title:
            title = self._search_regex(
                (r'<h1[^>]+class=["\'](title|videoTitle)["\'][^>]*>(?P<title>[^<]+)',
                 r'<div[^>]+data-video-title=(["\'])(?P<title>.+?)\1',
                 r'shareTitle\s*=\s*(["\'])(?P<title>.+?)\1'),
                webpage, 'title', group='title')

        return title

    def _extract_flashvars(self, webpage, video_id):
        """stub"""
        return self._parse_json(self._search_regex(
            r'var\s+flashvars_\d+\s*=\s*({.+?});', webpage, 'flashvars', default='{}'), video_id)

    def _extract_uploader(self, webpage):
        """stub"""

        # TODO: This fails for non-EN sites (e.g. fr.pornhubpremium.com).
        return self._html_search_regex(
            r'(?s)From:&nbsp;.+?<(?:a\b[^>]+\bhref=["\']/(?:(?:user|channel)s|model|pornstar)/|span\b[^>]+\bclass=["\']username)[^>]+>(.+?)<',
            webpage, 'uploader', fatal=False)

    def _extract_upload_date(self, video_urls):
        """stub"""
        upload_date = None

        for (url, _) in video_urls:
            if upload_date:
                break
            upload_date = self._search_regex(r'/(\d{6}/\d{2})/', url, 'upload data', default=None)

        # Strip
        if upload_date:
            upload_date = upload_date.replace('/', '')
        return upload_date

    def _extract_formats(self, video_urls, video_id):
        """stub"""
        formats = []

        for url, height in video_urls:
            if determine_ext(url) == 'mpd':
                formats.extend(self._extract_mpd_formats(url, video_id, mpd_id='dash', fatal=False))
                continue

            tbr = None
            mobj = re.search(r'(?P<height>\d+)[pP]?_(?P<tbr>\d+)[kK]', url)
            if mobj:
                tbr = int(mobj.group('tbr'))
                if not height:
                    height = int(mobj.group('height'))

            formats.append({
                'url': url,
                'format_id': '%dp' % height if height else None,
                'height': height,
                'tbr': tbr,
            })

        # Sort
        self._sort_formats(formats)

        return formats

    def _extract_list(self, webpage, meta_key):
        """stub"""
        div = self._search_regex(
            r'(?s)<div[^>]+\bclass=["\'].*?\b%sWrapper[^>]*>(.+?)</div>'
            % meta_key, webpage, meta_key, default=None)
        if not div:
            return None
        return re.findall(r'<a[^>]+\bhref=[^>]+>([^<]+)', div)

    def _extract_video(self, host, video_id):
        """stub"""

        # Set cookies
        self._set_cookie(host, 'age_verified', '1')
        self._set_cookie(host, 'platform', 'pc')

        # Fetch the video page
        webpage = self._download_webpage(
            'https://%s/view_video.php?viewkey=%s' % (host, video_id), video_id)

        # Not signed in
        if 'Log In And Access Premium Porn Videos' in webpage:
            self.raise_login_required()

        # Not a premium subscriber
        if 'Upgrade now to enjoy this video' in webpage:
            self.raise_login_required('This is a premium video')

        # Paid video
        if 'Buy on video player' in webpage:
            self.raise_login_required('This is a paid video')

        # Fan only video
        if 'Fan Only Video' in webpage:
            self.raise_login_required('This is a fan only video')

        # Check for other errors
        error_msg = self._html_search_regex(
            r'(?s)<div[^>]+class=(["\'])(?:(?!\1).)*\b(?:removed|userMessageSection)\b(?:(?!\1).)*\1[^>]*>(?P<error>.+?)</div>',
            webpage, 'error message', default=None, group='error')
        if error_msg:
            error_msg = re.sub(r'\s+', ' ', error_msg)
            raise ExtractorError(
                'PornHub said: %s' % error_msg, expected=True, video_id=video_id)

        # Video data
        title = self._extract_video_title(webpage)
        thumbnail = None
        duration = None
        upload_date = None
        video_urls = []
        video_urls_set = set()
        subtitles = {}

        # Read flash vars
        flashvars = self._extract_flashvars(webpage, video_id)

        # Get video info from flashvars
        if flashvars:
            thumbnail = flashvars.get('image_url')
            duration = int_or_none(flashvars.get('video_duration'))

            # Get subtitle info
            subtitle_url = url_or_none(flashvars.get('closedCaptionsFile'))
            if subtitle_url:
                subtitles.setdefault('en', []).append({
                    'url': subtitle_url,
                    'ext': 'srt',
                })

            # Get video info
            media_definitions = flashvars.get('mediaDefinitions')
            if isinstance(media_definitions, list):
                for definition in media_definitions:
                    if not isinstance(definition, dict):
                        continue
                    video_url = definition.get('videoUrl')
                    if not video_url or not isinstance(video_url, compat_str):
                        continue
                    if video_url in video_urls_set:
                        continue
                    video_urls_set.add(video_url)
                    video_urls.append((video_url, int_or_none(definition.get('quality'))))

        # Parsing issues
        # https://github.com/ytdl-org/youtube-dl/commit/79367a98208fbf01d6e04b6747a6e01d0b1f8b9a
        #
        # Todo: Abstract this section out into helpers.
        #
        if not video_urls:
            self._set_cookie(host, 'platform', 'tv')
            tv_webpage = self._download_webpage(
                'https://%s/view_video.php?viewkey=%s' % (host, video_id), video_id)

            assignments = self._search_regex(
                r'(var.+?mediastring.+?)</script>', tv_webpage,
                'encoded url').split(';')

            js_vars = {}

            def parse_js_value(inp):
                inp = re.sub(r'/\*(?:(?!\*/).)*?\*/', '', inp)
                if '+' in inp:
                    inps = inp.split('+')
                    return functools.reduce(
                        operator.concat, map(parse_js_value, inps))
                inp = inp.strip()
                if inp in js_vars:
                    return js_vars[inp]
                return remove_quotes(inp)

            for assn in assignments:
                assn = assn.strip()
                if not assn:
                    continue
                assn = re.sub(r'var\s+', '', assn)
                vname, value = assn.split('=', 1)
                js_vars[vname] = parse_js_value(value)

            video_url = js_vars['mediastring']
            if video_url not in video_urls_set:
                video_urls.append((video_url, None))
                video_urls_set.add(video_url)

        for mobj in re.finditer(
                r'<a[^>]+\bclass=["\']downloadBtn\b[^>]+\bhref=(["\'])(?P<url>(?:(?!\1).)+)\1',
                webpage):
            video_url = mobj.group('url')
            if video_url not in video_urls_set:
                video_urls.append((video_url, None))
                video_urls_set.add(video_url)

        # Get formats
        formats = self._extract_formats(video_urls, video_id)

        # Get upload date
        upload_date = self._extract_upload_date(video_urls)

        # Get uploader
        uploader = self._extract_uploader(webpage)

        # Get counts
        view_count = self._extract_count(
            r'<span class="count">([\d,\.\s]+)</span> views', webpage, 'view')
        like_count = self._extract_count(
            r'<span class="votesUp">([\d,\.\s]+)</span>', webpage, 'like')
        dislike_count = self._extract_count(
            r'<span class="votesDown">([\d,\.\s]+)</span>', webpage, 'dislike')
        comment_count = self._extract_count(
            r'(?s)<div id=\"cmtWrapper\">(:?.*?)\((?P<count>\d+)\)(?:.*?)</div>',
            webpage, 'comment', group='count')

        # Get tags
        tags = self._extract_list(webpage, 'tags')

        # Get categories
        categories = self._extract_list(webpage, 'categories')

        info_dict = {
            'id': video_id,
            'uploader': uploader,
            'upload_date': upload_date,
            'title': title,
            'thumbnail': thumbnail,
            'duration': duration,
            'view_count': view_count,
            'like_count': like_count,
            'dislike_count': dislike_count,
            'comment_count': comment_count,
            'formats': formats,
            'age_limit': 18,
            'tags': tags,
            'categories': categories,
            'subtitles': subtitles,
        }

        return info_dict

    @staticmethod
    def _extract_urls(webpage):
        return re.findall(
            r'src=[\"\'](?P<url>(?:https?:)?//(?:www\.)?pornhub(?:premium)?\.(?:com|net)/embed/(?P<id>[\da-z]+))[\"\']',
            webpage)

    @staticmethod
    def _is_authenticated(webpage):
        return 'href="/user/logout"' in webpage


class PornHubPremiumIE(PornHubPremiumBaseIE):
    """
    PornHubPremiumIE handles videos from pornhubpremium.com.
    """
    IE_DESC = 'PornHub Premium'
    _NETRC_MACHINE = 'pornhubpremium'
    _HOST = 'pornhubpremium.com'
    _LOGIN_URL = 'https://%s/premium/login' % _HOST
    _VALID_URL = r'''(?x)
                    https?://(?P<host>(?:[^/]+?\.)?pornhubpremium\.(?:com|net))/(?:view_video\.php\?viewkey=|embed/)(?P<id>[\da-z]+)
                    '''

    def _real_initialize(self):
        self._login(self._LOGIN_URL, self._HOST, self._NETRC_MACHINE, requires_login=True)

    def _real_extract(self, url):
        host, video_id = re.match(self._VALID_URL, url).groups()
        return self._extract_video(host, video_id)

    def _extract_video(self, host, video_id):
        """stub"""

        # Set cookies
        self._set_cookie(host, 'age_verified', '1')
        self._set_cookie(host, 'platform', 'pc')

        # Fetch the video page
        webpage = self._download_webpage(
            'https://%s/view_video.php?viewkey=%s' % (host, video_id), video_id)

        # Not signed in
        if 'Log In And Access Premium Porn Videos' in webpage:
            self.raise_login_required()

        # Not a premium subscriber
        if 'Upgrade now to enjoy this video' in webpage:
            self.raise_login_required('This is a premium video')

        # Paid video
        if 'Buy on video player' in webpage:
            self.raise_login_required('This is a paid video')

        # Fan only video
        if 'Fan Only Video' in webpage:
            self.raise_login_required('This is a fan only video')

        # Check for other errors
        error_msg = self._html_search_regex(
            r'(?s)<div[^>]+class=(["\'])(?:(?!\1).)*\b(?:removed|userMessageSection)\b(?:(?!\1).)*\1[^>]*>(?P<error>.+?)</div>',
            webpage, 'error message', default=None, group='error')
        if error_msg:
            error_msg = re.sub(r'\s+', ' ', error_msg)
            raise ExtractorError(
                'PornHub said: %s' % error_msg, expected=True, video_id=video_id)

        # Video data
        title = self._extract_video_title(webpage)
        thumbnail = None
        duration = None
        upload_date = None
        video_urls = []
        video_urls_set = set()
        subtitles = {}

        # Read flash vars
        flashvars = self._extract_flashvars(webpage, video_id)

        # Get video info from flashvars
        if flashvars:
            thumbnail = flashvars.get('image_url')
            duration = int_or_none(flashvars.get('video_duration'))

            # Get subtitle info
            subtitle_url = url_or_none(flashvars.get('closedCaptionsFile'))
            if subtitle_url:
                subtitles.setdefault('en', []).append({
                    'url': subtitle_url,
                    'ext': 'srt',
                })

            # Get video info
            media_definitions = flashvars.get('mediaDefinitions')
            if isinstance(media_definitions, list):
                for definition in media_definitions:
                    if not isinstance(definition, dict):
                        continue
                    video_url = definition.get('videoUrl')
                    if not video_url or not isinstance(video_url, compat_str):
                        continue
                    if video_url in video_urls_set:
                        continue
                    video_urls_set.add(video_url)
                    video_urls.append((video_url, int_or_none(definition.get('quality'))))

        # Parsing issues
        # https://github.com/ytdl-org/youtube-dl/commit/79367a98208fbf01d6e04b6747a6e01d0b1f8b9a
        #
        # Todo: Abstract this section out into helpers.
        #
        if not video_urls:
            assignments = self._search_regex(
                r'(var ra.+?var quality_\d\d\d\d?p=.+)', webpage,
                'encoded url').split(';')

            js_vars = {}

            def parse_js_value(inp):
                inp = re.sub(r'/\*(?:(?!\*/).)*?\*/', '', inp)
                if '+' in inp:
                    inps = inp.split('+')
                    return functools.reduce(
                        operator.concat, map(parse_js_value, inps))
                inp = inp.strip()
                if inp in js_vars:
                    return js_vars[inp]
                return remove_quotes(inp)

            for assn in assignments:
                assn = assn.strip()
                if not assn:
                    continue
                assn = re.sub(r'var\s+', '', assn)
                vname, value = assn.split('=', 1)
                js_vars[vname] = parse_js_value(value)

            for x in range(len(media_definitions)):
                media_definitions[x]['videoUrl'] = js_vars['media_{0}'.format(x)]

            if isinstance(media_definitions, list):
                for definition in media_definitions:
                    if not isinstance(definition, dict):
                        continue
                    video_url = definition.get('videoUrl')
                    if not video_url or not isinstance(video_url, compat_str):
                        continue
                    if video_url in video_urls_set:
                        continue
                    video_urls_set.add(video_url)
                    video_urls.append((video_url, int_or_none(definition.get('quality'))))

        for mobj in re.finditer(
                r'<a[^>]+\bclass=["\']downloadBtn\b[^>]+\bhref=(["\'])(?P<url>(?:(?!\1).)+)\1',
                webpage):
            video_url = mobj.group('url')
            if video_url not in video_urls_set:
                video_urls.append((video_url, None))
                video_urls_set.add(video_url)

        # Get formats
        formats = self._extract_formats(video_urls, video_id)

        # Get upload date
        upload_date = self._extract_upload_date(video_urls)

        # Get uploader
        uploader = self._extract_uploader(webpage)

        # Get counts
        view_count = self._extract_count(
            r'<span class="count">([\d,\.\s]+)</span> views', webpage, 'view')
        like_count = self._extract_count(
            r'<span class="votesUp">([\d,\.\s]+)</span>', webpage, 'like')
        dislike_count = self._extract_count(
            r'<span class="votesDown">([\d,\.\s]+)</span>', webpage, 'dislike')
        comment_count = self._extract_count(
            r'(?s)<div id=\"cmtWrapper\">(:?.*?)\((?P<count>\d+)\)(?:.*?)</div>',
            webpage, 'comment', group='count')

        # Get tags
        tags = self._extract_list(webpage, 'tags')

        # Get categories
        categories = self._extract_list(webpage, 'categories')

        info_dict = {
            'id': video_id,
            'uploader': uploader,
            'upload_date': upload_date,
            'title': title,
            'thumbnail': thumbnail,
            'duration': duration,
            'view_count': view_count,
            'like_count': like_count,
            'dislike_count': dislike_count,
            'comment_count': comment_count,
            'formats': formats,
            'age_limit': 18,
            'tags': tags,
            'categories': categories,
            'subtitles': subtitles,
        }

        return info_dict


class PornHubPlaylistPremiumBaseIE(PornHubPremiumIE):
    def _extract_entries(self, webpage, host):
        # Only process container div with main playlist content skipping
        # drop-down menu that uses similar pattern for videos (see
        # https://github.com/ytdl-org/youtube-dl/issues/11594).
        container = self._search_regex(
            r'(?s)(<div[^>]+class=["\']container.+)', webpage,
            'container', default=webpage)

        return [
            self.url_result(
                'http://www.%s/%s' % (host, video_url),
                PornHubPremiumIE.ie_key(), video_title=title)
            for video_url, title in orderedSet(re.findall(
                r'href="/?(view_video\.php\?.*\bviewkey=[\da-z]+[^"]*)"[^>]*\s+title="([^"]+)"',
                container))
        ]

    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        host = mobj.group('host')
        playlist_id = mobj.group('id')

        webpage = self._download_webpage(url, playlist_id)

        entries = self._extract_entries(webpage, host)

        playlist = self._parse_json(
            self._search_regex(
                r'(?:playlistObject|PLAYLIST_VIEW)\s*=\s*({.+?});', webpage,
                'playlist', default='{}'),
            playlist_id, fatal=False)
        title = playlist.get('title') or self._search_regex(
            r'>Videos\s+in\s+(.+?)\s+[Pp]laylist<', webpage, 'title', fatal=False)

        return self.playlist_result(
            entries, playlist_id, title, playlist.get('description'))


class PornHubUserPremiumIE(PornHubPlaylistPremiumBaseIE):
    _VALID_URL = r'(?P<url>https?://(?:[^/]+\.)?pornhubpremium\.(?:com|net)/(?:(?:user|channel)s|model|pornstar)/(?P<id>[^/?#&]+))(?:[?#&]|/(?!videos)|$)'
    _TESTS = [{
        'url': 'https://www.pornhubpremium.com/model/zoe_ph',
        'playlist_mincount': 118,
    }, {
        'url': 'https://www.pornhubpremium.com/pornstar/liz-vicious',
        'info_dict': {
            'id': 'liz-vicious',
        },
        'playlist_mincount': 118,
    }, {
        'url': 'https://www.pornhubpremium.com/users/russianveet69',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/channels/povd',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/model/zoe_ph?abc=1',
        'only_matching': True,
    }]

    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        user_id = mobj.group('id')
        return self.url_result(
            '%s/videos' % mobj.group('url'), ie=PornHubPagedVideoListPremiumIE.ie_key(),
            video_id=user_id)


class PornHubPagedPlaylistPremiumBaseIE(PornHubPlaylistPremiumBaseIE):
    @staticmethod
    def _has_more(webpage):
        return re.search(
            r'''(?x)
                <li[^>]+\bclass=["\']page_next|
                <link[^>]+\brel=["\']next|
                <button[^>]+\bid=["\']moreDataBtn
            ''', webpage) is not None

    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        host = mobj.group('host')
        item_id = mobj.group('id')

        page = int_or_none(self._search_regex(
            r'\bpage=(\d+)', url, 'page', default=None))

        entries = []
        for page_num in (page, ) if page is not None else itertools.count(1):
            try:
                webpage = self._download_webpage(
                    url, item_id, 'Downloading page %d' % page_num,
                    query={'page': page_num})
            except ExtractorError as e:
                if isinstance(e.cause, compat_HTTPError) and e.cause.code == 404:
                    break
                raise
            page_entries = self._extract_entries(webpage, host)
            if not page_entries:
                break
            entries.extend(page_entries)
            if not self._has_more(webpage):
                break

        return self.playlist_result(orderedSet(entries), item_id)


class PornHubPagedVideoListPremiumIE(PornHubPagedPlaylistPremiumBaseIE):
    _VALID_URL = r'https?://(?:[^/]+\.)?(?P<host>pornhubpremium\.(?:com|net))/(?P<id>(?:[^/]+/)*[^/?#&]+)'
    _TESTS = [{
        'url': 'https://www.pornhubpremium.com/model/zoe_ph/videos',
        'only_matching': True,
    }, {
        'url': 'http://www.pornhubpremium.com/users/rushandlia/videos',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/pornstar/jenny-blighe/videos',
        'info_dict': {
            'id': 'pornstar/jenny-blighe/videos',
        },
        'playlist_mincount': 149,
    }, {
        'url': 'https://www.pornhubpremium.com/pornstar/jenny-blighe/videos?page=3',
        'info_dict': {
            'id': 'pornstar/jenny-blighe/videos',
        },
        'playlist_mincount': 40,
    }, {
        # default sorting as Top Rated Videos
        'url': 'https://www.pornhubpremium.com/channels/povd/videos',
        'info_dict': {
            'id': 'channels/povd/videos',
        },
        'playlist_mincount': 293,
    }, {
        # Top Rated Videos
        'url': 'https://www.pornhubpremium.com/channels/povd/videos?o=ra',
        'only_matching': True,
    }, {
        # Most Recent Videos
        'url': 'https://www.pornhubpremium.com/channels/povd/videos?o=da',
        'only_matching': True,
    }, {
        # Most Viewed Videos
        'url': 'https://www.pornhubpremium.com/channels/povd/videos?o=vi',
        'only_matching': True,
    }, {
        'url': 'http://www.pornhubpremium.com/users/zoe_ph/videos/public',
        'only_matching': True,
    }, {
        # Most Viewed Videos
        'url': 'https://www.pornhubpremium.com/pornstar/liz-vicious/videos?o=mv',
        'only_matching': True,
    }, {
        # Top Rated Videos
        'url': 'https://www.pornhubpremium.com/pornstar/liz-vicious/videos?o=tr',
        'only_matching': True,
    }, {
        # Longest Videos
        'url': 'https://www.pornhubpremium.com/pornstar/liz-vicious/videos?o=lg',
        'only_matching': True,
    }, {
        # Newest Videos
        'url': 'https://www.pornhubpremium.com/pornstar/liz-vicious/videos?o=cm',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/pornstar/liz-vicious/videos/paid',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/pornstar/liz-vicious/videos/fanonly',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/video',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/video?page=3',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/video/search?search=123',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/categories/teen',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/categories/teen?page=3',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/hd',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/hd?page=3',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/described-video',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/described-video?page=2',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/video/incategories/60fps-1/hd-porn',
        'only_matching': True,
    }, {
        'url': 'https://www.pornhubpremium.com/playlist/44121572',
        'info_dict': {
            'id': 'playlist/44121572',
        },
        'playlist_mincount': 132,
    }, {
        'url': 'https://www.pornhubpremium.com/playlist/4667351',
        'only_matching': True,
    }, {
        'url': 'https://de.pornhubpremium.com/playlist/4667351',
        'only_matching': True,
    }]

    @classmethod
    def suitable(cls, url):
        return (False
                if PornHubPremiumIE.suitable(url) or PornHubUserPremiumIE.suitable(url) or PornHubUserVideosUploadPremiumIE.suitable(url)
                else super(PornHubPagedVideoListPremiumIE, cls).suitable(url))


class PornHubUserVideosUploadPremiumIE(PornHubPagedPlaylistPremiumBaseIE):
    _VALID_URL = r'(?P<url>https?://(?:[^/]+\.)?(?P<host>pornhubpremium\.(?:com|net))/(?:(?:user|channel)s|model|pornstar)/(?P<id>[^/]+)/videos/upload)'
    _TESTS = [{
        'url': 'https://www.pornhubpremium.com/pornstar/jenny-blighe/videos/upload',
        'info_dict': {
            'id': 'jenny-blighe',
        },
        'playlist_mincount': 129,
    }, {
        'url': 'https://www.pornhubpremium.com/model/zoe_ph/videos/upload',
        'only_matching': True,
    }]
