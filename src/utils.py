from openai import APIStatusError, AuthenticationError, OpenAI, RateLimitError
import rich


def check_key(key, model="gpt-4o-mini") -> str | None:
    """
    Check if the API key is valid.
    """
    try:
        client = OpenAI(api_key=key)

        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a yeser, you only output lowercase yes.",
                },
                {"role": "user", "content": "yes or no? say yes"},
            ],
        )
        result = completion.choices[0].message.content
        rich.print(f"🔑 [bold green]available key[/bold green]: [orange_red1]'{key}'[/orange_red1] ({result})\n")
        return "yes"
    except AuthenticationError as e:
        rich.print(f"[deep_sky_blue1]{e.body['code']} ({e.status_code})[/deep_sky_blue1]: '{key}'") # type: ignore
        return e.body["code"] # type: ignore
    except RateLimitError as e:
        rich.print(f"[deep_sky_blue1]{e.body['code']} ({e.status_code})[/deep_sky_blue1]: '{key}'") # type: ignore
        return e.body["code"] # type: ignore
    except APIStatusError as e:
        rich.print(f"[bold red]{e.body['code']} ({e.status_code})[/bold red]: '{key}'") # type: ignore
        return e.body["code"] # type: ignore
    except Exception as e:
        rich.print(f"[bold red]{e}[/bold red]: '{key}'") # type: ignore
        return "Unknown Error"

if __name__ == "__main__":
    check_key("sk-proj-12345")
