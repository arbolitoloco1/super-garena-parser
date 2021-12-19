from mwrogue.esports_client import EsportsClient
from mwrogue import wiki_time, wiki_time_parser
import requests
from datetime import datetime, timezone
from pytz import timezone, utc

site = EsportsClient("lol")

rpgid = input()

match_data_and_timeline = site.get_data_and_timeline(rpgid)
match_data = match_data_and_timeline[0]
match_timeline = match_data_and_timeline[1]

patch = match_data["gameVersion"]
patch = ".".join(patch.split(".", 2)[:2])
ddragon_patch = patch + ".1"

runes = requests.get(f"https://raw.communitydragon.org/{patch}/plugins/rcp-be-lol-game-data/global/default/v1/perks.json")
runes = runes.json()
champions = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{ddragon_patch}/data/en_US/champion.json")
champions = champions.json()["data"]
items = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{ddragon_patch}/data/en_US/item.json")
items = items.json()["data"]
spells = requests.get(f"https://ddragon.leagueoflegends.com/cdn/{ddragon_patch}/data/en_US/summoner.json")
spells = spells.json()["data"]

champion_ids = {}
spell_ids = {}
rune_ids = {
    8000: "Precision",
    8100: "Domination",
    8200: "Sorcery",
    8300: "Inspiration",
    8400: "Resolve"
}
item_ids = {}

for key, champion in champions.items():
    champion_ids[int(champion["key"])] = champion["name"]

for key, spell in spells.items():
    spell_ids[int(spell["key"])] = spell["name"]

for rune in runes:
    rune_ids[rune["id"]] = rune["name"]

for key, item in items.items():
    item_ids[int(key)] = item["name"]

item_ids[0] = ""

game_length = int(match_data["gameDuration"])
minutes = int(game_length / 60)
seconds = int(game_length % 60)
game_length_pretty = f"{minutes:d}:{seconds:02d}"
game_start_timestamp = int(match_data["gameStartTimestamp"] / 1000)
game_start = datetime.utcfromtimestamp(game_start_timestamp)
kst = timezone("Asia/Seoul")
kst_object = game_start.astimezone(kst)
start_date = kst_object.strftime("%Y-%m-%d")
start_time = kst_object.strftime("%H:%M")

matchschedule_info = site.cargo_client.query(
    tables="MatchScheduleGame=MSG, MatchSchedule=MS, Tournaments=T",
    fields="MSG.Blue, MSG.Red, MSG.Winner, MS.DateTime_UTC, MS.DST, MS.OverviewPage, T.StandardName",
    where=f"MSG.RiotPlatformGameId = '{rpgid.upper()}'",
    join_on="MSG.MatchId = MS.MatchId, MS.OverviewPage=T.OverviewPage"
)
if len(matchschedule_info) > 1 or len(matchschedule_info) == 0:
    print("More than one game found in data!")
    exit()

matchschedule_info = matchschedule_info[0]
blue_team = matchschedule_info["Blue"]
red_team = matchschedule_info["Red"]
winner_data = matchschedule_info["Winner"]
dst = matchschedule_info["DST"]
tournament = matchschedule_info["StandardName"]

for team in match_data["teams"]:
    if team["win"] == True or team["win"] == "Win":
        winner_team_id = int(team["teamId"])

if winner_team_id == 100:
    winner = "1"
elif winner_team_id == 200:
    winner = "2"
else:
    print("No winner team could be found!")
    exit()

teamstats = {"team1": {}, "team2": {}}

for team in match_data["teams"]:
    if team["teamId"] == 100:
        team_key = "team1"
    elif team["teamId"] == 200:
        team_key = "team2"
    else:
        print("Invalid team!")
        exit()
    for i, ban in enumerate(team["bans"]):
        i += 1
        teamstats[team_key]["ban" + str(i)] = champion_ids[ban["championId"]] or "None"
    teamstats[team_key]["barons"] = str(team["objectives"]["baron"]["kills"])
    teamstats[team_key]["kills"] = str(team["objectives"]["champion"]["kills"])
    teamstats[team_key]["riftHerald"] = str(team["objectives"]["riftHerald"]["kills"])
    teamstats[team_key]["towers"] = str(team["objectives"]["tower"]["kills"])
    teamstats[team_key]["inhibitor"] = str(team["objectives"]["inhibitor"]["kills"])
    teamstats[team_key]["infernal"] = 0
    teamstats[team_key]["cloud"] = 0
    teamstats[team_key]["mountain"] = 0
    teamstats[team_key]["ocean"] = 0
    teamstats[team_key]["chemtech"] = 0
    teamstats[team_key]["hextech"] = 0
    teamstats[team_key]["elder"] = 0
    teamstats[team_key]["totaldrakes"] = 0

team_drakes = {}

drake_names = {
    "FIRE_DRAGON": "infernal",
    "AIR_DRAGON": "cloud",
    "EARTH_DRAGON": "mountain",
    "WATER_DRAGON": "ocean",
    "CHEMTECH_DRAGON": "chemtech",
    "HEXTECH_DRAGON": "hextech",
    "ELDER_DRAGON": "elder"
}

for frame in match_timeline["frames"]:
    for event in frame["events"]:
        if event["type"] == "ELITE_MONSTER_KILL":
            if event["monsterType"] == "DRAGON":
                drake = drake_names[event["monsterSubType"]]
                killer_team = event["killerTeamId"]
                if killer_team == 100:
                    drake_type_kills = teamstats["team1"].get(drake) or 0
                    teamstats["team1"][drake] = drake_type_kills + 1
                    drake_kills = teamstats["team1"].get("totaldrakes") or 0
                    teamstats["team1"]["totaldrakes"] = drake_kills + 1
                elif killer_team == 200:
                    drake_type_kills = teamstats["team2"].get(drake) or 0
                    teamstats["team2"][drake] = drake_type_kills + 1
                    drake_kills = teamstats["team2"].get("totaldrakes") or 0
                    teamstats["team2"]["totaldrakes"] = drake_kills + 1

participantstats = []

for participant in match_data["participants"]:
    participantinfo = {"id": participant["participantId"], "team_id": participant["teamId"],
                       "name": participant["summonerName"].split(" ")[1],
                       "champion": champion_ids[participant["championId"]], "kills": str(participant["kills"]),
                       "deaths": str(participant["deaths"]), "assists": str(participant["assists"]),
                       "gold": str(int(participant["goldEarned"])),
                       "cs": str(int(participant["totalMinionsKilled"]) or 0 +
                                 int(participant["neutralMinionsKilled"]) or 0),
                       "vision": str(int(participant["visionScore"])),
                       "damagetochamps": str(int(participant["totalDamageDealtToChampions"])),
                       "spell1": spell_ids[participant["spell1Id"]], "spell2": spell_ids[participant["spell2Id"]],
                       "primary": rune_ids[participant["perks"]["styles"][0]["style"]],
                       "secondary": rune_ids[participant["perks"]["styles"][1]["style"]],
                       "primary_1": rune_ids[participant["perks"]["styles"][0]["selections"][0]["perk"]],
                       "primary_2": rune_ids[participant["perks"]["styles"][0]["selections"][1]["perk"]],
                       "primary_3": rune_ids[participant["perks"]["styles"][0]["selections"][2]["perk"]],
                       "primary_4": rune_ids[participant["perks"]["styles"][0]["selections"][3]["perk"]],
                       "secondary_1": rune_ids[participant["perks"]["styles"][1]["selections"][0]["perk"]],
                       "secondary_2": rune_ids[participant["perks"]["styles"][1]["selections"][1]["perk"]],
                       "defense": rune_ids[participant["perks"]["statPerks"]["defense"]],
                       "flex": rune_ids[participant["perks"]["statPerks"]["flex"]],
                       "offense": rune_ids[participant["perks"]["statPerks"]["offense"]],
                       "pentakills": str(participant["pentaKills"])}
    participant_items = {}
    for x in range(0, 6):
        try:
            participantinfo[f"item{str(x + 1)}"] = item_ids[participant[f"item{str(x)}"]]
        except KeyError:
            print(f"Error with item id {participant[f'item{str(x)}']}")
    participantinfo["trinket"] = item_ids[participant["item6"]]
    participantstats.append(participantinfo)

for participant in participantstats:
    participant_teamid = participant["team_id"]
    if participant_teamid == 100:
        totalGold = teamstats["team1"].get("totalGold") or 0
        teamstats["team1"]["totalGold"] = totalGold + int(participant["gold"])
    elif participant_teamid == 200:
        totalGold = teamstats["team2"].get("totalGold") or 0
        teamstats["team2"]["totalGold"] = totalGold + int(participant["gold"])

template_start = f"""{{{{Scoreboard/Header|{blue_team}|{red_team}}}}}
{{{{Scoreboard/Season 8|tournament={tournament} |patch={str(patch)} |winner={winner} 
|gamelength={game_length_pretty} |timezone=KST 
|date={start_date} |dst={dst} |time={start_time} |rpgid={rpgid.upper()} |vodlink= """

template_team1 = f"""|team1={blue_team} |team1g={str(teamstats["team1"]["totalGold"])} 
|team1k={teamstats["team1"]["kills"]} |team1d={teamstats["team1"]["totaldrakes"]} |team1b={teamstats["team1"]["barons"]}  
|team1t={teamstats["team1"]["towers"]} |team1rh={teamstats["team1"]["riftHerald"]} 
|team1i={teamstats["team1"]["inhibitor"]}  |team1cloud={teamstats["team1"]["cloud"]}  
|team1infernal={teamstats["team1"]["infernal"]} |team1mountain={teamstats["team1"]["mountain"]}  
|team1ocean={teamstats["team1"]["ocean"]} |team1elder={teamstats["team1"]["elder"]} 
|team1hextech={teamstats["team1"]["hextech"]} |team1chemtech={teamstats["team1"]["chemtech"]} 
|team1ban1={teamstats["team1"]["ban1"]} |team1ban2={teamstats["team1"]["ban2"]} |team1ban3={teamstats["team1"]["ban3"]}
|team1ban4={teamstats["team1"]["ban4"]} |team1ban5={teamstats["team1"]["ban5"]}
"""

template_team2 = f"""|team2={red_team} |team2g={str(teamstats["team2"]["totalGold"])} 
|team2k={teamstats["team2"]["kills"]} |team2d={teamstats["team2"]["totaldrakes"]} |team2b={teamstats["team2"]["barons"]}  
|team2t={teamstats["team2"]["towers"]} |team2rh={teamstats["team2"]["riftHerald"]} 
|team2i={teamstats["team2"]["inhibitor"]}  |team2cloud={teamstats["team2"]["cloud"]}  
|team2infernal={teamstats["team2"]["infernal"]} |team2mountain={teamstats["team2"]["mountain"]}  
|team2ocean={teamstats["team2"]["ocean"]} |team2elder={teamstats["team2"]["elder"]} 
|team2hextech={teamstats["team2"]["hextech"]} |team2chemtech={teamstats["team2"]["chemtech"]} 
|team2ban1={teamstats["team2"]["ban1"]} |team2ban2={teamstats["team2"]["ban2"]} |team2ban3={teamstats["team2"]["ban3"]}
|team2ban4={teamstats["team2"]["ban4"]} |team2ban5={teamstats["team2"]["ban5"]}
"""

participantids_dict = {
    1: "blue1",
    2: "blue2",
    3: "blue3",
    4: "blue4",
    5: "blue5",
    6: "red1",
    7: "red2",
    8: "red3",
    9: "red4",
    10: "red5"
}

template_players_blue = ""
template_players_red = ""
template_list = []

for participant in participantstats:
    participant_key = participantids_dict[participant["id"]]
    template = f"""|{participant_key}={{{{Scoreboard/Player|link={participant["name"]}
|champion={participant["champion"]}  |kills= {participant["kills"]} |deaths={participant["deaths"]}
|assists={participant["assists"]} |gold={participant["gold"]} |cs={participant["cs"]} 
|visionscore={participant["vision"]} |damagetochamps={participant["damagetochamps"]}
|summonerspell1={participant["spell1"]} |summonerspell2={participant["spell2"]} |keystone={participant["primary_1"]}  
|primary={participant["primary"]} |secondary={participant["secondary"]} |trinket={participant["trinket"]} 
|pentakills={participant["pentakills"]} |item1={participant["item1"]} |item2={participant["item2"]} 
|item3={participant["item3"]} |item4={participant["item4"]} |item5={participant["item5"]} 
|item6={participant["item6"]} 
|runes={{{{Scoreboard/Player/Runes|{participant["primary_1"]},{participant["primary_2"]},{participant["primary_3"]},
{participant["primary_4"]},{participant["secondary_1"]},{participant["secondary_2"]},{participant["offense"]},
{participant["flex"]},{participant["defense"]}}}}}}}}}"""
    if participant["id"] <= 5:
        template_players_blue += template
    else:
        template_players_red += template

final_template = template_start + template_team1 + template_players_blue + template_team2 + template_players_red + \
                 "\n}}"
print(final_template)
