import secrets

async def coinflip_game():
    
    flip_result = secrets.choice(["heads", "tails"])
    return flip_result

async def dice_roll_game():
   
    roll_result = secrets.choice([1, 2, 3, 4, 5, 6])
    return roll_result

