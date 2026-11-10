"""Loot statistics labels, CSV totals and the statistics window."""

import csv
import os
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd

class StatsPanelMixin:
    """Loot statistics labels, CSV totals and the statistics window. Mixin for BotGUI."""

    def update_loot_stats(self, loot_data):
        """Update loot statistics with new loot data"""
        self.total_gold += loot_data['gold']
        self.total_elixir += loot_data['elixir']
        self.total_dark_elixir += loot_data['dark_elixir']
        self.attacks_with_loot += 1

        # Update labels
        self.gold_label.config(text=f"{self.total_gold:,}")
        self.elixir_label.config(text=f"{self.total_elixir:,}")
        self.dark_elixir_label.config(text=f"{self.total_dark_elixir:,}")
        self.attacks_label.config(text=str(self.attacks_with_loot))

        # Update averages
        if self.attacks_with_loot > 0:
            self.avg_gold_label.config(text=f"{self.total_gold // self.attacks_with_loot:,}")
            self.avg_elixir_label.config(text=f"{self.total_elixir // self.attacks_with_loot:,}")
            self.avg_dark_label.config(text=f"{self.total_dark_elixir // self.attacks_with_loot:,}")

    def update_skipped_stats(self, skipped_bases, attacked_bases):
        """Update skipped bases and skip/attack ratio statistics in the GUI."""
        self.skipped_bases = skipped_bases
        #self.skipped_label.config(text=str(skipped_bases))
        if attacked_bases > 0:
            skip_ratio = skipped_bases / attacked_bases
        else:
            skip_ratio = 0.0
        self.skip_ratio = skip_ratio

    def reset_loot_stats(self):
        """Reset all loot statistics"""
        self.total_gold = 0
        self.total_elixir = 0
        self.total_dark_elixir = 0
        self.attacks_with_loot = 0
        #self.skipped_bases = 0
        self.skip_ratio = 0.0
        
        # Reset labels
        self.gold_label.config(text="0")
        self.elixir_label.config(text="0")
        self.dark_elixir_label.config(text="0")
        self.trophies_label.config(text="0")
        self.attacks_label.config(text="0")
        #self.skipped_label.config(text="0")
        #self.skip_ratio_label.config(text="0.00")
        self.avg_gold_label.config(text="0")
        self.avg_elixir_label.config(text="0")
        self.avg_dark_label.config(text="0")
        self.avg_trophies_label.config(text="0")
        
        self.log_message("Loot statistics reset")

    def update_csv_totals(self):
        """Read loot_tracking.csv and update total plundered stats in the GUI."""
        gold = 0
        elixir = 0
        dark = 0
        try:
            if os.path.exists('loot_tracking.csv'):
                with open('loot_tracking.csv', 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        gold += int(row.get('gold', 0))
                        elixir += int(row.get('elixir', 0))
                        dark += int(row.get('dark_elixir', 0))
        except Exception as e:
            print(f"Error reading loot_tracking.csv: {e}")
        self.csv_gold = gold
        self.csv_elixir = elixir
        self.csv_dark_elixir = dark
        self.csv_gold_label.config(text=f"Total Gold: {gold:,}")
        self.csv_elixir_label.config(text=f"Total Elixir: {elixir:,}")
        self.csv_dark_label.config(text=f"Total Dark Elixir: {dark:,}")

    def show_statistics(self):
        """Plot trophies and loops completed from loot_tracking.csv"""
        try:
            df = pd.read_csv('loot_tracking.csv', parse_dates=['timestamp'])
        except Exception as e:
            self.log_message(f"Error reading loot_tracking.csv: {e}")
            return
        if df.empty:
            self.log_message("No data to plot.")
            return
        now = datetime.now()
        periods = {
            'Day': now - timedelta(days=1),
            'Week': now - timedelta(weeks=1),
            'Month': now - timedelta(days=30)
        }
        plt.figure(figsize=(15, 10))
        for i, (label, start_time) in enumerate(periods.items(), 1):
            plt.subplot(2, 2, i)
            mask = df['timestamp'] >= start_time.strftime('%Y-%m-%d %H:%M:%S')
            sub = df[mask]
            if sub.empty:
                plt.title(f"No data for last {label.lower()}")
                continue
            plt.plot(sub['timestamp'], sub['trophies'], marker='o', label='Trophies')
            plt.xlabel('Time')
            plt.ylabel('Trophies')
            plt.title(f'Trophies in the last {label.lower()}' )
            plt.xticks(rotation=45)
            plt.legend()
        # Plot loops completed (attack_number)
        plt.subplot(2, 2, 4)
        plt.plot(df['timestamp'], df['attack_number'], marker='x', color='orange', label='Loops Completed')
        plt.xlabel('Time')
        plt.ylabel('Loop #')
        plt.title('Loops Completed Over Time')
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()
        plt.show()
        self.log_message("Statistics plotted.")
