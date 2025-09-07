using Microsoft.AspNetCore.Mvc;
using System.ComponentModel.DataAnnotations;
using System.Security.Claims;
using Microsoft.AspNetCore.Authentication;
using Microsoft.AspNetCore.Authentication.Cookies;
using Microsoft.AspNetCore.Authorization;

var builder = WebApplication.CreateBuilder(args);

// Add services
builder.Services.AddControllers();
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.WithOrigins("http://localhost:7125")
              .AllowAnyMethod()
              .AllowAnyHeader()
              .AllowCredentials();
    });
});

// Add authentication
builder.Services.AddAuthentication(CookieAuthenticationDefaults.AuthenticationScheme)
    .AddCookie(options =>
    {
        options.LoginPath = "/login";
        options.LogoutPath = "/logout";
        options.Cookie.Name = "BookAppAuth";
        options.Cookie.HttpOnly = true;
        options.Cookie.SameSite = SameSiteMode.None;
        options.Cookie.SecurePolicy = CookieSecurePolicy.SameAsRequest;
        options.ExpireTimeSpan = TimeSpan.FromHours(24);
        options.Events.OnRedirectToLogin = context =>
        {
            context.Response.StatusCode = 401;
            return Task.CompletedTask;
        };
    });

builder.Services.AddAuthorization();

// Add singleton services
builder.Services.AddSingleton<IUserService, InMemoryUserService>();
builder.Services.AddSingleton<IBookService, InMemoryBookService>();

var app = builder.Build();

// Configure pipeline
app.UseCors();
app.UseDefaultFiles();
app.UseStaticFiles();
app.UseAuthentication();
app.UseRouting();
app.UseAuthorization();
app.MapControllers();

app.Run();

// Models
public class Book
{
    public int Id { get; set; }
    
    [Required]
    public string Title { get; set; } = string.Empty;
    
    [Required]
    public string Author { get; set; } = string.Empty;
    
    public string UserId { get; set; } = string.Empty;
}

public class BookRequest
{
    [Required]
    public string Title { get; set; } = string.Empty;
    
    [Required]
    public string Author { get; set; } = string.Empty;
}

public class LoginRequest
{
    [Required]
    public string Username { get; set; } = string.Empty;
    
    [Required]
    public string Password { get; set; } = string.Empty;
}

public class User
{
    public string Id { get; set; } = string.Empty;
    public string Username { get; set; } = string.Empty;
    public string PasswordHash { get; set; } = string.Empty;
}

public class AuthStatusResponse
{
    public bool IsAuthenticated { get; set; }
    public string Username { get; set; } = string.Empty;
}

// Services
public interface IUserService
{
    User? ValidateUser(string username, string password);
    User? GetUserById(string id);
}

public interface IBookService
{
    List<Book> GetUserBooks(string userId);
    Book AddBook(BookRequest bookRequest, string userId);
}

public class InMemoryUserService : IUserService
{
    private readonly List<User> _users = new();

    public InMemoryUserService()
    {
        // Add demo users (in production, use proper password hashing)
        _users.AddRange(new[]
        {
            new User { Id = "1", Username = "demo", PasswordHash = HashPassword("demo123") },
            new User { Id = "2", Username = "admin", PasswordHash = HashPassword("admin123") },
            new User { Id = "3", Username = "john", PasswordHash = HashPassword("john123") }
        });
    }

    public User? ValidateUser(string username, string password)
    {
        var user = _users.FirstOrDefault(u => u.Username == username);
        if (user != null && VerifyPassword(password, user.PasswordHash))
        {
            return user;
        }
        return null;
    }

    public User? GetUserById(string id)
    {
        return _users.FirstOrDefault(u => u.Id == id);
    }

    private string HashPassword(string password)
    {
        // Simple hash for demo - use BCrypt or similar in production
        return Convert.ToBase64String(System.Text.Encoding.UTF8.GetBytes(password + "salt"));
    }

    private bool VerifyPassword(string password, string hash)
    {
        return HashPassword(password) == hash;
    }
}

public class InMemoryBookService : IBookService
{
    private readonly List<Book> _books = new();
    private int _nextId = 1;

    public InMemoryBookService()
    {
        // Add sample books for different users
        _books.AddRange(new[]
        {
            new Book { Id = _nextId++, Title = "The Great Gatsby", Author = "F. Scott Fitzgerald", UserId = "1" },
            new Book { Id = _nextId++, Title = "To Kill a Mockingbird", Author = "Harper Lee", UserId = "1" },
            new Book { Id = _nextId++, Title = "1984", Author = "George Orwell", UserId = "2" },
            new Book { Id = _nextId++, Title = "Pride and Prejudice", Author = "Jane Austen", UserId = "2" }
        });
    }

    public List<Book> GetUserBooks(string userId)
    {
        return _books.Where(b => b.UserId == userId).ToList();
    }

    public Book AddBook(BookRequest bookRequest, string userId)
    {
        var book = new Book
        {
            Id = _nextId++,
            Title = bookRequest.Title,
            Author = bookRequest.Author,
            UserId = userId
        };
        
        _books.Add(book);
        return book;
    }
}

// Controllers
[ApiController]
[Route("api/[controller]")]
public class AuthController : ControllerBase
{
    private readonly IUserService _userService;

    public AuthController(IUserService userService)
    {
        _userService = userService;
    }

    [HttpPost("login")]
    public async Task<IActionResult> Login([FromForm] LoginRequest loginRequest)
    {
        if (!ModelState.IsValid)
        {
            return BadRequest("<div class='error-message'>Please fill in all fields.</div>");
        }

        var user = _userService.ValidateUser(loginRequest.Username, loginRequest.Password);
        if (user == null)
        {
            return BadRequest("<div class='error-message'>Invalid username or password.</div>");
        }

        // Create claims for the user
        var claims = new List<Claim>
        {
            new Claim(ClaimTypes.Name, user.Username),
            new Claim(ClaimTypes.NameIdentifier, user.Id)
        };

        var claimsIdentity = new ClaimsIdentity(claims, CookieAuthenticationDefaults.AuthenticationScheme);
        var authProperties = new AuthenticationProperties
        {
            IsPersistent = true,
            ExpiresUtc = DateTimeOffset.UtcNow.AddHours(24)
        };

        await HttpContext.SignInAsync(
            CookieAuthenticationDefaults.AuthenticationScheme,
            new ClaimsPrincipal(claimsIdentity),
            authProperties);

        return Ok($"<div class='login-success' data-username='{user.Username}'>Login successful!</div>");
    }

    [HttpPost("logout")]
    [Authorize]
    public async Task<IActionResult> Logout()
    {
        await HttpContext.SignOutAsync(CookieAuthenticationDefaults.AuthenticationScheme);
        return Ok("Logged out successfully");
    }

    [HttpGet("status")]
    public IActionResult GetAuthStatus()
    {
        if (User.Identity?.IsAuthenticated == true)
        {
            return Ok(new AuthStatusResponse 
            { 
                IsAuthenticated = true, 
                Username = User.Identity.Name ?? "Unknown" 
            });
        }

        return Ok(new AuthStatusResponse { IsAuthenticated = false });
    }
}

[ApiController]
[Route("api/[controller]")]
//[Authorize]
public class BooksController : ControllerBase
{
    private readonly IBookService _bookService;

    public BooksController(IBookService bookService)
    {
        _bookService = bookService;
    }

    [HttpGet]
    public IActionResult GetBooks()
    {
        var userId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        if (string.IsNullOrEmpty(userId))
        {
            return Unauthorized("User not authenticated");
        }

        var books = _bookService.GetUserBooks(userId);
        
        if (!books.Any())
        {
            return Ok("""
                <div class="empty-state">
                    <svg fill="currentColor" viewBox="0 0 20 20">
                        <path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                    </svg>
                    <h3>No books yet!</h3>
                    <p>Add your first book using the form above.</p>
                </div>
                """);
        }

        var booksHtml = string.Join("", books.Select(book => $"""
            <div class="book-item">
                <div class="book-title">{System.Web.HttpUtility.HtmlEncode(book.Title)}</div>
                <div class="book-author">by {System.Web.HttpUtility.HtmlEncode(book.Author)}</div>
            </div>
            """));

        return Ok(booksHtml);
    }

    [HttpPost]
    public IActionResult AddBook([FromForm] BookRequest bookRequest)
    {
        var userId = User.FindFirst(ClaimTypes.NameIdentifier)?.Value;
        if (string.IsNullOrEmpty(userId))
        {
            return Unauthorized("User not authenticated");
        }

        if (!ModelState.IsValid)
        {
            return BadRequest("Please fill in all fields.");
        }

        try
        {
            _bookService.AddBook(bookRequest, userId);
            
            // Return updated book list for this user
            return GetBooks();
        }
        catch (Exception ex)
        {
            return StatusCode(500, $"Error adding book: {ex.Message}");
        }
    }
}