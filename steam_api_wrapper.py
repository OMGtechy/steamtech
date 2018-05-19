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

        return self.get_key_from_dict(here, 'games', response)
