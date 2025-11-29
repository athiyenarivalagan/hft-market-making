import databento as db

# Load local DBN file
store = db.DBNStore.from_file("data/raw/CLX5_mbo.dbn")

# Convert to DataFrame then CSV
df = store.to_df()
df.to_csv("data/processed/CLX5_mbo.txt", index=False)
print("Converted CLX5_mbo.dbn ➜ CLX5_mbo.txt")