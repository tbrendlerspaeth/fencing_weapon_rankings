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
BETA = 400 # higher: increased change in new Elo, lower: decreased change in new Elo 
ELO_DECAY = 1 # number of points to decay fencers' Elos by every time duel occurs
ELO_FLOOR = 1 # lower threshold for Elo
BOUNTY_CONSTANT = K / 2 # Note: due to the way the calculation works, max bounty bonus
# will be half the above BOUNTY_CONSTANT val.

#####
class fencer:
    
    def __init__(self, name, rankings_df):
        
        self.name = name
        self.is_ranked = self.name in rankings_df.FencerName.values
     
        if self.is_ranked:
            self.ranked_status = "ranked"
            self.original_elo = self.get_col_value(rankings_df, "OriginalElo")
            self.old_elo = self.get_col_value(rankings_df, "CurrentElo")
            self.level = self.get_col_value(rankings_df, "Level")
            self.old_duel_number = self.get_col_value(rankings_df, "NumberOfDuels")

        else: 
            self.ranked_status = "unranked"
            self.level = input(f"Please input level (beginner/experienced/advanced) for fencer {self.name}: ")
            self.old_elo = self.assign_elo(rankings_df)
            self.original_elo = self.old_elo
            self.old_duel_number = 0
        
        self.new_duel_number = self.old_duel_number + 1 

        ### attrs to be updated
        self.new_elo = 0


    def get_col_value(self, rankings_df, column):
        col_value = rankings_df.loc[rankings_df.FencerName == self.name, column].values[0]
        return col_value
    

    def assign_elo(self, rankings_df):
        elo_quant_dict = {"beginner" : 0.2,
                        "experienced": 0.5,
                        "advanced": 0.75}
        return round(rankings_df.CurrentElo.quantile(q=elo_quant_dict[self.level]))


class duel:

    def __init__(self, winner, loser, weapon, rankings_df, duel_log, elo_tracking_log, k, beta):

        self.winner = fencer(winner, rankings_df)
        self.loser = fencer(loser, rankings_df)
        self.weapon = weapon
        self.rankings_df_old = rankings_df
        self.duel_date = date.today()
        self.duel_log_old = duel_log
        self.elo_tracking_log_old = elo_tracking_log
        self.k = k
        self.beta = beta

        ### attrs to be updated
        self.rankings_df_new = pd.DataFrame()
        self.duel_log_new = pd.DataFrame()
        self.elo_tracking_log_new = pd.DataFrame()
    
    def get_new_elos(self, bounty_constant, elo_floor):
        # calculate the probabilities of expected wins
        winner_expected = 1 / (1 + 10**((self.loser.old_elo - self.winner.old_elo) / self.beta))
        loser_expected = 1 - winner_expected
        
        # calculate the new elo rankings
        winner_new_elo = self.winner.old_elo + self.k * (1 - winner_expected)
        loser_new_elo = self.loser.old_elo + self.k * (0 - loser_expected)

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
        
        self.winner.new_elo = round(winner_new_elo + winner_bounty)
        self.loser.new_elo = round(loser_new_elo + loser_bounty)

    def update_elo_ranking(self, fencer):

        # distinguish between ranked and unkranked fencers.
        # for ranked: update their record. for unranked: make new record
        # and append to existing log
        if fencer.is_ranked:
            # Find the row in the DataFrame that corresponds to the fencer's name
            mask = self.rankings_df_new["FencerName"] == fencer.name
            
            # Update the fencer's elo in the DataFrame
            self.rankings_df_new.loc[mask, 'CurrentElo'] = fencer.new_elo 
            # Update the fencer's duel number in the DataFrame
            self.rankings_df_new.loc[mask, 'NumberOfDuels'] = fencer.new_duel_number

        else:
            unranked_fencer_deets = {"FencerName": fencer.name,
                                    "Weapon": self.weapon,
                                    "OriginalElo": fencer.old_elo, 
                                    "CurrentElo": fencer.new_elo,
                                    "Level": fencer.level,
                                    "NumberOfDuels": fencer.new_duel_number}

            self.rankings_df_new = self.rankings_df_new.append(unranked_fencer_deets, ignore_index=True)
        
        # sort df by rankings in descending order
        self.rankings_df_new.sort_values('CurrentElo', ascending=False, inplace=True)

    def update_duel_log(self):
       
        self.duel_log_new = self.duel_log_old
        update_duel_deets = {"WinnerName": self.winner.name,	
                            "LoserName": self.loser.name,	
                            "Weapon": self.weapon,
                            "DuelDate": self.duel_date}
        self.duel_log_new = self.duel_log_new.append(update_duel_deets, ignore_index=True)

    def update_elo_tracking_log(self):
      
        self.elo_tracking_log_new = self.elo_tracking_log_old
        fencers = (self.winner, self.loser)
        for fencer in fencers:
            update_elo_tracking_deets = {"FencerName": fencer.name, 
                                        "Weapon": self.weapon, 
                                        "OriginalWeaponElo": fencer.original_elo,
                                        "OldWeaponElo": fencer.old_elo, 
                                        "NewWeaponElo": fencer.new_elo,
                                        "EloDifference": fencer.new_elo - fencer.old_elo, 
                                        "DuelDate": self.duel_date}
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

        # print loser details
        print("\nLoser's details")
        print("Name: ", self.loser.name)
        print("Ranked status: ", self.loser.ranked_status)
        print("Level: ", self.loser.level)
        print(f"Loser's Elo will be updated from {self.loser.old_elo} to {self.loser.new_elo}.")
        print(f"Number of {self.weapon} duels completed: ", self.loser.new_duel_number)

    def update_csv_files(self, weapon_ranking_csv, duel_log_csv, elo_tracking_csv):
        # overwrite existing files with their updated versions.
        self.rankings_df_new.to_csv(weapon_ranking_csv, index=False)
        self.duel_log_new.to_csv(duel_log_csv, index=False)
        self.elo_tracking_log_new.to_csv(elo_tracking_csv, index=False)
    
    def set_to_floor_elo(self, floor_elo_value):
        # set current 
        self.rankings_df_new["CurrentElo"] = [floor_elo_value if x < floor_elo_value 
                                              else x for x in self.rankings_df_new["CurrentElo"]]
        

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
        my_duel = duel(winner_name, loser_name, weapon, rankings_df, duel_log_df, elo_tracking_df, K, BETA)
      
        # get new elos
        my_duel.get_new_elos(bounty_constant=BOUNTY_CONSTANT, elo_floor=ELO_FLOOR)
        
        # decay elos
        my_duel.rankings_df_new = my_duel.rankings_df_old
        my_duel.rankings_df_new["CurrentElo"] = my_duel.rankings_df_new["CurrentElo"] - ELO_DECAY
        # round off the rankings
        my_duel.rankings_df_new["CurrentElo"] = my_duel.rankings_df_new["CurrentElo"].round()

        # update the duellists' rankings
        my_duel.update_elo_ranking(my_duel.winner)
        my_duel.update_elo_ranking(my_duel.loser)

        #TODO: check for CurrentElo 0 and set any to 1.
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
