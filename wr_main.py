"""
Weapon Rankings main script.
"""

from datetime import date
import math

import pandas as pd

#####
# FILE PATHS
FOIL_RANKINGS_PATH = "Foil_Weapon_Rankings.csv"
EPEE_RANKINGS_PATH = "Epee_Weapon_Rankings.csv"
SABRE_RANKINGS_PATH = "Sabre_Weapon_Rankings.csv"
DUEL_LOG = "WR_Duel_Log.csv"
ELO_TRACKING = "Elo_Tracking_Log.csv"


# CONSTANTS
K = 20 # constant factor to determine how much ratings change after a match
BETA = 800 # lower: increased change in new Elo, higher: decreased change in new Elo 
ELO_DECAY = K*0.1 # number of points to decay fencers' Elos by every time duel occurs
ELO_FLOOR = 1 # lower threshold for Elo
BOUNTY_CONSTANT = K / 1.5 # Note: due to the way the calculation works, max bounty bonus
# will be half the above BOUNTY_CONSTANT val.
PROBATION_MATCHES = 0.4 # number of probation matches a new fencer must complete equal to set
# proportion of total fencers in particular weapon ranking
PROBATION_MULTIPLIER = 0.75 # multiplication modifier for elo calculation for new fencers on probation
WS_ELORATIO_THRESH = 0.6 # loserElo / winnerElo cut-off for winstreak alteration


#####
class fencer:
    
    def __init__(self, name, rankings_df, probation_matches, opponent_name, elo_tracking_log, weapon):
        
        self.elo_tracking_log = elo_tracking_log
        self.weapon = weapon
        self.name = name
        # determine if fencer already has a ranking for duel weapon
        self.is_ranked = self.name in rankings_df.FencerName.values
     
        # set all fencer attributes from weapon ranking if ranked
        if self.is_ranked:
            self.ranked_status = "ranked"
            self.original_elo = self.get_col_value(rankings_df, "OriginalRankingPoints")
            self.old_elo = self.get_col_value(rankings_df, "CurrentRankingPoints")
            self.level = self.get_col_value(rankings_df, "Level")
            self.old_duel_number = self.get_col_value(rankings_df, "NumberOfDuels")
            self.old_probation_matches = self.get_col_value(rankings_df, "ProbationMatches")
            self.old_winstreak = self.get_col_value(rankings_df, "CurrentWinstreak")
            self.longest_winstreak = self.get_col_value(rankings_df, "LongestWinstreak")
           
        # assign unranked fencer attributes
        else: 
            self.ranked_status = "unranked"
            self.level = input(f"Please input level (beginner/experienced) for fencer {self.name}: ")
            self.old_elo = round(rankings_df["CurrentRankingPoints"].median(), 1)
            self.original_elo = self.old_elo
            self.old_duel_number = 0
            self.old_probation_matches = round(probation_matches * rankings_df.shape[0])
            self.old_winstreak = 0
            self.longest_winstreak = 0

        # assign attributes independent of whether fencer ranked or not
        self.is_on_probation = self.old_probation_matches > 0
        self.new_duel_number = self.old_duel_number + 1 
        self.opponent_name = opponent_name
        self.new_probation_matches = self.assign_new_probation_matches()

        ### attrs to be updated
        self.new_elo = 0
        self.new_winstreak = 0
        

    def get_col_value(self, rankings_df, column):
        col_value = rankings_df.loc[rankings_df.FencerName == self.name, column].values[0]
        return col_value
    

    def assign_new_probation_matches(self):
        # select only fencer entries for elo tracking log  
        opponent_list = self.elo_tracking_log[
            self.elo_tracking_log["FencerName"] == self.name]
        # select only the duel weapon for the above fencer entries
        opponent_list = opponent_list.loc[opponent_list["Weapon"] == self.weapon]

        if self.old_probation_matches == 0:
            return 0
        
        elif self.opponent_name in opponent_list.OpponentName.values:
            return self.old_probation_matches
        
        else:
            return self.old_probation_matches - 1

###
class duel:

    def __init__(self, winner, loser, weapon, rankings_df, duel_log, elo_tracking_log, k, beta, 
                 probation_matches, probation_multiplier, ws_eloratio_thresh):

        self.elo_tracking_log_old = elo_tracking_log
        self.winner = fencer(winner, rankings_df, probation_matches, loser, elo_tracking_log, weapon)
        self.loser = fencer(loser, rankings_df, probation_matches, winner, elo_tracking_log, weapon)
        self.weapon = weapon
        self.rankings_df_old = rankings_df
        self.duel_date = date.today()
        self.duel_log_old = duel_log
        self.k = k
        self.beta = beta
        self.probation_multiplier = probation_multiplier
        self.ws_eloratio_thresh = ws_eloratio_thresh

        ### attrs to be updated
        self.rankings_df_new = pd.DataFrame()
        self.duel_log_new = pd.DataFrame()
        self.elo_tracking_log_new = pd.DataFrame()
    
    def get_new_elos(self, bounty_constant, elo_floor):
        # calculate the probabilities of expected wins
        winner_expected = (1 / (1 + 10**((self.loser.old_elo - self.winner.old_elo) / self.beta))) 
        loser_expected = 1 - winner_expected
        
        # calculate the new elo rankings
        winner_new_elo = self.winner.old_elo + (self.k * (1 - winner_expected)) * self.probation_mult(self.winner) * self.ws_multiplier()
        loser_new_elo = self.loser.old_elo + (self.k * (0 - loser_expected)) * self.probation_mult(self.loser)

        # experience bounty bonus
        bounty_const = bounty_constant
        # calculate the elo ratios
        winner_elo_ratio = self.loser.old_elo / self.winner.old_elo
        loser_elo_ratio = self.winner.old_elo / self.loser.old_elo
        
        # calculate added experience bounty value
        winner_bounty = (1 / (1 + math.e**(- winner_elo_ratio)) - 0.5) * bounty_const
        loser_bounty = (1 / (1 + math.e**(- loser_elo_ratio)) - 0.5) * bounty_const

        # ensure loser elo does not go below ELO_FLOOR
        # done for the benefit of the print duel details otherwise it will be an inaccurate 
        # value if new elo goes below the ELO_FLOOR
        elo_floor=elo_floor
        if loser_new_elo < elo_floor:
            loser_new_elo = elo_floor
        else:
            loser_new_elo = loser_new_elo
        
        self.winner.new_elo = round(winner_new_elo + winner_bounty, 1)
        self.loser.new_elo = round(loser_new_elo + loser_bounty, 1)

    def probation_mult(self, fencer):
        if fencer.is_on_probation:
            return self.probation_multiplier
        else:
            return 1

    def update_weapon_ranking(self, fencer):

        # distinguish between ranked and unkranked fencers.
        # for ranked: update their record. for unranked: make new record
        # and append to existing log
        if fencer.is_ranked:
            # Find the row in the DataFrame that corresponds to the fencer's name
            mask = self.rankings_df_new["FencerName"] == fencer.name
            
            # Update the fencer's elo in weapon rankings DataFrame
            self.rankings_df_new.loc[mask, 'CurrentRankingPoints'] = fencer.new_elo 
            # Update the fencer's duel number in weapon rankings DataFrame
            self.rankings_df_new.loc[mask, 'NumberOfDuels'] = fencer.new_duel_number
            # Update the fencer's probation matches in weapon rankings DataFrame
            self.rankings_df_new.loc[mask, "ProbationMatches"] = fencer.new_probation_matches
            # Update the fencer's winstreak values in weapon rankings DataFrame
            self.rankings_df_new.loc[mask, "CurrentWinstreak"] = fencer.new_winstreak
            self.rankings_df_new.loc[mask, "LongestWinstreak"] = fencer.longest_winstreak

        # If fencer is unranked, update the details by adding them as a new row in the
        # rankings DataFrame
        else:
            unranked_fencer_deets = {"FencerName": fencer.name,
                                    "Weapon": self.weapon,
                                    "OriginalRankingPoints": fencer.old_elo, 
                                    "CurrentRankingPoints": fencer.new_elo,
                                    "Level": fencer.level,
                                    "NumberOfDuels": fencer.new_duel_number,
                                    "ProbationMatches": fencer.new_probation_matches,
                                    "CurrentWinstreak": fencer.new_winstreak,
                                    "LongestWinstreak": fencer.longest_winstreak
                                    }

            self.rankings_df_new = self.rankings_df_new.append(unranked_fencer_deets, ignore_index=True)
        
        # sort df by rankings in descending order
        self.rankings_df_new.sort_values('CurrentRankingPoints', ascending=False, inplace=True)

    def update_winstreaks(self):
        # Determine the new winstreak values for the both fencers.
        if self.winner.old_elo < self.loser.old_elo:
            # update the current winstreak values
            self.loser.new_winstreak = 0
            self.winner.new_winstreak = self.winner.old_winstreak + 1
            # update the longest winstreak values
            self.loser.longest_winstreak = self.loser.old_winstreak
            self.winner.longest_winstreak = self.winner.new_winstreak

        elif self.loser.old_elo / self.winner.old_elo >= self.ws_eloratio_thresh:
            # same as above
            # update the current winstreak values
            self.loser.new_winstreak = 0
            self.winner.new_winstreak = self.winner.old_winstreak + 1
            # update the longest winstreak values
            self.loser.longest_winstreak = self.loser.old_winstreak
            self.winner.longest_winstreak = self.winner.new_winstreak

        else:
            # everything remains unchanged
            self.loser.new_winstreak = self.loser.old_winstreak
            self.winner.new_winstreak = self.winner.old_winstreak
            self.loser.longest_winstreak = self.loser.longest_winstreak
            self.winner.longest_winstreak = self.winner.longest_winstreak

    def ws_multiplier(self):
        # Calculate the winstreak elo multiplier for the winner
        return 1 + (1 / (1 + math.e**(-(self.winner.new_winstreak / self.k))) - 0.5)

    def update_duel_log(self):
       
        self.duel_log_new = self.duel_log_old
        update_duel_deets = {"WinnerName": self.winner.name,	
                            "LoserName": self.loser.name,	
                            "Weapon": self.weapon,
                            "DuelDate": self.duel_date}
        self.duel_log_new = self.duel_log_new.append(update_duel_deets, ignore_index=True)

    def update_elo_tracking_log(self):
        # update the tracking low with duel details
        self.elo_tracking_log_new = self.elo_tracking_log_old
        fencers = (self.winner, self.loser)
        for fencer in fencers:
            update_elo_tracking_deets = {"FencerName": fencer.name, 
                                        "OpponentName": fencer.opponent_name,
                                        "Weapon": self.weapon, 
                                        "OriginalWeaponElo": fencer.original_elo,
                                        "OldWeaponElo": fencer.old_elo, 
                                        "NewWeaponElo": fencer.new_elo,
                                        "EloDifference": round(fencer.new_elo - fencer.old_elo, 1), 
                                        "DuelDate": self.duel_date,
                                        "CurrentWinstreak": fencer.new_winstreak,
                                        "LongestWinstreak": fencer.longest_winstreak}
            self.elo_tracking_log_new = self.elo_tracking_log_new.append(update_elo_tracking_deets, ignore_index=True)

    
    def print_duel_deets(self):
       # print duel weapon
        print("\nDuel weapon: ", self.weapon)

        # print winner details
        print("\nWinner's details")
        print("Name: ", self.winner.name)
        print("Ranked status: ", self.winner.ranked_status)
        print("Level: ", self.winner.level)
        print(f"Winner's Elo will be updated from {self.winner.old_elo} to {self.winner.new_elo}.")
        print(f"Number of {self.weapon} duels completed: ", self.winner.new_duel_number)
        print("Number of probation matches to complete: ", self.winner.new_probation_matches)
        print(f"Winstreak changed from {self.winner.old_winstreak} to {self.winner.new_winstreak}.")
        print("Longest winstreak is", self.winner.longest_winstreak)

        # print loser details
        print("\nLoser's details")
        print("Name: ", self.loser.name)
        print("Ranked status: ", self.loser.ranked_status)
        print("Level: ", self.loser.level)
        print(f"Loser's Elo will be updated from {self.loser.old_elo} to {self.loser.new_elo}.")
        print(f"Number of {self.weapon} duels completed: ", self.loser.new_duel_number)
        print("Number of probation matches to complete: ", self.loser.new_probation_matches)
        print(f"Winstreak changed from {self.loser.old_winstreak} to {self.loser.new_winstreak}.")
        print("Longest winstreak is", self.loser.longest_winstreak)

    def update_csv_files(self, weapon_ranking_csv, duel_log_csv, elo_tracking_csv):
        # overwrite existing files with their updated versions.
        self.rankings_df_new.to_csv(weapon_ranking_csv, index=False)
        self.duel_log_new.to_csv(duel_log_csv, index=False)
        self.elo_tracking_log_new.to_csv(elo_tracking_csv, index=False)
    
    def set_to_floor_elo(self, floor_elo_value):
        # set current 
        self.rankings_df_new["CurrentRankingPoints"] = [floor_elo_value if x < floor_elo_value 
                                              else x for x in self.rankings_df_new["CurrentRankingPoints"]]
        

def main():
    while True:
        # input data of duel
        weapon = input("Please type the duel weapon (foil/epee/sabre): ")
        winner_name = input("Please type in the winner's name: ")
        loser_name = input("Please type in the loser's name: ")
    
        # read in all the csv files
        weapon_rankings_files = {"foil": FOIL_RANKINGS_PATH,
                                "epee": EPEE_RANKINGS_PATH,
                                "sabre": SABRE_RANKINGS_PATH}

        rankings_df = pd.read_csv(weapon_rankings_files[weapon])
        duel_log_df = pd.read_csv(DUEL_LOG)
        elo_tracking_df = pd.read_csv(ELO_TRACKING)
      
        # initialise the duel
        my_duel = duel(winner_name, loser_name, weapon, rankings_df, duel_log_df, elo_tracking_df, K, BETA, PROBATION_MATCHES, PROBATION_MULTIPLIER, WS_ELORATIO_THRESH)

        # update the winstreak values for both fencers
        my_duel.update_winstreaks()

        # get new elos
        my_duel.get_new_elos(bounty_constant=BOUNTY_CONSTANT, elo_floor=ELO_FLOOR)
        
        # decay elos
        my_duel.rankings_df_new = my_duel.rankings_df_old
        my_duel.rankings_df_new["CurrentRankingPoints"] = my_duel.rankings_df_new["CurrentRankingPoints"] - ELO_DECAY
        
        # round off the rankings
        my_duel.rankings_df_new["CurrentRankingPoints"] = my_duel.rankings_df_new["CurrentRankingPoints"].round(decimals=1)

        # update the duellists' rankings
        my_duel.update_weapon_ranking(my_duel.winner)
        my_duel.update_weapon_ranking(my_duel.loser)

        #TODO: check for CurrentRankingPoints 0 and set any to 1.
        my_duel.set_to_floor_elo(floor_elo_value=ELO_FLOOR)

        # update duel log
        my_duel.update_duel_log()
      
        # update elo tracking
        my_duel.update_elo_tracking_log()
      
        # print duel details to screen and ask user to confirm they are correct
        my_duel.print_duel_deets()
        user_confirmation = input("Do you confirm the duel's details as correct? (y/n) ")

        if user_confirmation == "y":
            # update the csv logs with new duel outcome information
            my_duel.update_csv_files(weapon_rankings_files[weapon], DUEL_LOG, ELO_TRACKING)
            print("\nDuel logs have been updated. You may input information for another duel or quit the program.\n")
            print(my_duel.rankings_df_new)
            continue
        else:
            print("Details not correct? Try inputting again or quit the program.")
            continue


#####
if __name__=="__main__":

    main()
