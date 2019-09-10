from steam_api_wrapper import SteamAPIWrapper
import discord
import re
import functools
import datetime

class SteamTechyClient(discord.Client):
    PREFIX_HOOK = 'steamtech ...'
    PREFIX_GAME_QUERY = "what games does "
    PREFIX_USER_QUERY = "tell me about "
    PREFIX_TIME_QUERY = "how much time has "

    def __init__(self, steam_token):
        self.steam_api_wrapper = SteamAPIWrapper(steam_token)
        super().__init__()

    async def on_ready(self):
        print('I\'m ready to go!')

    async def on_message(self, message):
        if message.content.lower().startswith(self.PREFIX_HOOK):
            await message.channel.send(self.determine_channel_response(message))

    def determine_channel_response(self, message):
        # this is to prevent the bot getting into an infinite loop
        # by talking to itself, just in case there's a bug / evil user
        if message.author == self.user:
            return 'Talking to yourself is the first sign of madness.'

        text = message.content[len(self.PREFIX_HOOK):].strip().lower()

        if not text:
            return 'Yes?'
        
        if text.startswith(self.PREFIX_GAME_QUERY):
            return self.determine_game_query_response(message)

        if text.startswith(self.PREFIX_USER_QUERY):
            return self.determine_summary_response(message)

        if text.startswith(self.PREFIX_TIME_QUERY):
            return self.determine_time_response(message)

        return r'¯\_(ツ)_/¯'

    def strip_whitespace_and_prefixes(self, message_content, command_prefix, remove_end_question_mark): 
        text = message_content[len(self.PREFIX_HOOK) + len(command_prefix):].strip()
        if remove_end_question_mark:
            while text.endswith('?'):
                text = text[:-1].strip()

        return text

    def extract_user_and_keywords(self, message, command_prefix, fill_between_user_and_keywords):
        text = self.strip_whitespace_and_prefixes(message.content, command_prefix, True).lower()
        captures = text.split()

        if len(captures) < 1:
            return False, 'I couldn\'t work out what user you were talking about.', None, None

        user = captures[0]

        capture_index = 1

        if fill_between_user_and_keywords:
            while len(fill_between_user_and_keywords) != 0:
                # yes, there's an edge case where having the next term be
                # (nothing) will break things, but nothing does that ... yet
                captured_term = '(nothing)'
                next_term = fill_between_user_and_keywords.pop(0)

                if len(captures) >= capture_index + 1:
                    captured_term = captures[capture_index]

                if captured_term != next_term:
                    return False, f'expected {next_term}, got {captured}', user, None

                capture_index += 1

        if len(captures) < capture_index + 1:
            return False, f'I couldn\'t work out what you\'re asking me about {user}.', user, None

        keywords = captures[capture_index:]

        return True, None, user, keywords

    def determine_time_response(self, message):
        success, error_message, user, keywords = self.extract_user_and_keywords(message, self.PREFIX_TIME_QUERY, ['wasted', 'on'])

        if not success:
            return error_message

        # yes, that's right, all games on steam
        all_games = self.steam_api_wrapper.get_all_steam_games()

        # anyone wanna tweet #bruteforce ?
        game_name = ' '.join(keywords)
        game_entry = next(game for game in all_games if game_name == game.get('name', None).lower())

        # now we have the entry, we can get the appid out of it
        # yep, we just got every single game off of steam for a single appid
        # guessing we'll go to hell for this
        game_appid = game_entry['appid']
        games_owned = self.steam_api_wrapper.get_games_owned_by_user(user)
        matching_game = next(game for game in games_owned if game_appid == game['appid'])

        time_spent = datetime.timedelta(minutes = matching_game['playtime_forever'])
        time_spent_hours, remainder = divmod(time_spent.total_seconds(), 3600)
        time_spent_minutes, remainder = divmod(remainder, 60)

        return f'```' + f'{int(time_spent_hours)} hours(s), {int(time_spent_minutes)} minute(s)' + '```'

    def determine_game_query_response(self, message):
        success, error_message, user, keywords = self.extract_user_and_keywords(message, self.PREFIX_GAME_QUERY, None)
        if not success:
            return error_message

        if len(keywords) > 1:
            return f'Trailing keywords: expected 1, got {len(keywords)} ({keywords})'

        return self.determine_game_query_response_based_on_keyword(user, keywords[0])

    def determine_game_query_response_based_on_keyword(self, user, keyword):
        if keyword == 'play':
            if user.lower() == 'ratstool':
                # ;)
                recent_games = [{'name': 'PLAYERUNKNOWN\'S BATTLEGROUNDS', 'playtime_2weeks': 20160}]
            else:
                recent_games = self.steam_api_wrapper.get_recently_played_games(user)

            entries = None

            if recent_games:
                def game_to_name(game):
                    name_key = 'name'
                    if name_key in game:
                        return game[name_key]
                    
                    appid = game['appid']
                    return f'Steam AppID {appid}'

                def longest_name_finder(current_max, candidate):
                    name = game_to_name(candidate)
                    name_length = len(name)

                    if current_max > name_length:
                        return current_max
                    
                    return name_length

                longest_name = functools.reduce(longest_name_finder, recent_games, 0)

                def game_to_playtime(game):
                    playtime = game['playtime_2weeks']
                    suffix = 'minutes' if playtime > 1 else 'minute'
                    return f'{playtime} {suffix} in the last 2 weeks'

                def game_to_padded_name(game):
                    game_name = game_to_name(game)
                    return game_name + (' ' * (longest_name - len(game_name)))

                entries = [f'{game_to_padded_name(game)} ({game_to_playtime(game)})' for game in recent_games]

            was_empty = False
            if not entries:
                was_empty = True
                entries = [f'{user} hasn\'t played any Steam games in the past 2 weeks']

            if user.lower() == 'spacejock':
                entries.insert(0, f'Typical...' if was_empty else f'Well fancy that, {user}\'s not trying to break the bot today!')

            return '```' + '\n'.join(entries) + '```'

        return f'I don\'t know what {keyword} means, but you appear to be referring to {user}.'

    def determine_summary_response(self, message):
        return self.determine_summary_response_for_user(message.content[len(self.PREFIX_HOOK) + len(self.PREFIX_USER_QUERY):].strip().lower())

    def determine_summary_response_for_user(self, user):
        player_summary = self.steam_api_wrapper.get_summary_data_for_user(user)

        steamid = player_summary['steamid']
        nickname = player_summary['personaname']
        profile_url = player_summary['profileurl']
        private = player_summary['communityvisibilitystate'] != 3
        private_display = 'Yes' if private else 'No'

        def get_private_entry(entry):
            if entry in player_summary:
                return player_summary[entry]
            else:
                return None

        real_name = get_private_entry('realname')
        game_info = get_private_entry('gameextrainfo')

        return '```\n' + '\n'.join(filter(None, [
                   f'Profile:      {profile_url}',
                   f'Username:     {user}',
                   f'Nickname:     {nickname}',
                   f'SteamID:      {steamid}',
                   f'Private:      {private_display}',
            (None, f'Real name:    {real_name}')[real_name != None],
            (None, f'Current game: {game_info}')[game_info != None]
        ])) + '```'

if __name__ == "__main__":
    settings = {}

    with open('steamtech.config', 'r') as config_file:
        for line in config_file:
            # note that this...
            # (a) doesn't check for duplicates
            # (b) doesn't check the config file is valid (it'll just crash / do the wrong thing)
            data = line.split()
            key = data[0]
            value = data[1]
            settings[key] = value

    discord_token = settings['discord_token']
    steam_token = settings['steam_token']

    client = SteamTechyClient(steam_token)
    client.run(discord_token)
