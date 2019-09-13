import valve.steam.api.interface

class SteamAPIError(IOError):
    def __init__(self, message):
        super().__init__(message)

class SteamAPINoResultError(SteamAPIError):
    def __init__(self, where):
        super().__init__(f'{where}: Didn\'t get a result.')

class SteamAPIMissingKeyError(SteamAPIError):
    def __init__(self, where, key, dict):
        super().__init__(f'{where}: Expected key {key}. Details: {dict}')

class SteamAPIUnexpectedValueError(SteamAPIError):
    def __init__(self, where, key, expected, dict):
        super().__init__(f'{where}: Expected value {expected} for key {key}. Details: {dict}')

class SteamAPIWrapper:
    def __init__(self, steam_token):
        self.raw_api = valve.steam.api.interface.API(steam_token)

    def steam_user(self):
        return self.raw_api['ISteamUser']

    def steam_player_service(self):
        return self.raw_api['IPlayerService']

    def steam_store_service(self):
        return self.raw_api['IStoreService']

    def get_response_from_result(self, where, dict):
        return self.get_key_from_dict(where, 'response', dict)

    def get_key_from_dict(self, where, key, dict):
        if not dict:
            raise SteamAPINoResultError(where)

        response = dict[key] if key in dict else None

        if not response:
            raise SteamAPIMissingKeyError(where, key, dict)

        return response

    def ensure_value_for_key(self, where, key, required_value, result):
        kv = self.get_key_from_dict(where, key, result)

        if kv != required_value:
            raise SteamAPIUnexpectedValueError(where, key, required_value, result)

    def get_steamid_for_user(self, user):
        here = f'ResolveVanityURL({user})'
        response = self.get_response_from_result(here, self.steam_user().ResolveVanityURL(user))
        self.ensure_value_for_key(here, 'success', 1, response)
        return self.get_key_from_dict(here, 'steamid', response)
        
    def get_summary_data_for_user(self, user):
        steamid = self.get_steamid_for_user(user)

        error_prefix = f'GetPlayerSummaries({steamid})'
        result = self.steam_user().GetPlayerSummaries(steamid)

        if not result:
            raise SteamAPIError(f'{error_prefix} Didn\'t get a result.')

        error_suffix = f'Details: {result}'
        response = result['response']

        if not response:
            raise SteamAPIError(f'{error_prefix} Expected a response entry in the result, but there wasn\'t one. {error_suffix}')

        players = response['players']
        if not players:
            raise SteamAPIError(f'{error_prefix} Got no players array back. {error_suffix}')

        if len(players) != 1:
            raise SteamAPIError(f'{error_prefix} Expected 1 player back, got {len(players)}. {error_suffix}')

        player = players[0]
        if not player:
            raise SteamAPIError(f'{error_prefix} Player object invalid. {error_suffix}')

        return player

    def get_recently_played_games(self, user):
        steamid = self.get_steamid_for_user(user)

        # 0 means all
        count = 0

        here = f'GetRecentlyPlayedGames({count}, {steamid}):'
        response = self.get_response_from_result(here, self.steam_player_service().GetRecentlyPlayedGames(count, steamid))

        response_count = self.get_key_from_dict(here, 'total_count', response)
        if response_count == 0:
            return None

        return self.get_key_from_dict(here, 'games', response)

    def get_all_steam_games(self):
        def get_chunk(last_appid):
            include_games = True
            include_dlc = False
            include_software = False
            include_videos = False
            include_hardware = False

            here = f'GetAppListi({include_games}, {include_dlc}, {include_software}, {include_videos}, {include_hardware}, {last_appid})'
            return self.get_response_from_result(here, self.steam_store_service().GetAppList(
                include_games = include_games,
                include_dlc = include_dlc,
                include_software = include_software,
                include_videos = include_videos,
                include_hardware = include_hardware,
                last_appid = last_appid
            ))

        games = []
        last_appid = 0
        get_more = True
        while get_more:
            chunk = get_chunk(last_appid)
            games += chunk['apps']
            get_more = chunk.get('have_more_results', False)
            last_appid = chunk.get('last_appid', None)

        return games

    def get_games_owned_by_user(self, user):
        steamid = self.get_steamid_for_user(user)
        include_appinfo = False
        include_played_free_games = True
        appids_filter = 0

        here = f'GetOwnedGames({steamid}, {include_appinfo}, {include_played_free_games}, {appids_filter})'
        response = self.get_response_from_result(here, self.steam_player_service().GetOwnedGames(
            steamid = steamid,
            include_appinfo = include_appinfo,
            include_played_free_games = include_played_free_games,
            appids_filter = appids_filter
        ))

        response_count = self.get_key_from_dict(here, 'game_count', response)
        if response_count == 0:
            return None

        return self.get_key_from_dict(here, 'games', response)
