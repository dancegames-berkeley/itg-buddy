import discord


async def edit_response(
    inter_or_msg: discord.Interaction | discord.Message, **kwargs
):
    if isinstance(inter_or_msg, discord.Interaction):
        await inter_or_msg.edit_original_response(**kwargs)
    elif isinstance(inter_or_msg, discord.Message):
        await inter_or_msg.edit(**kwargs)
    else:
        raise ValueError("inter_or_msg is not Interaction or Message")
